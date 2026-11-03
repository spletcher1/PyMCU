#!/usr/bin/env python3
"""Replays recorded FLIC data through PyMCU's adaptive baseline (docs/adaptive-baseline-plan.md, S3).

For each DFM data file in the run folders given, every Well's records go through BaselineTracker as
PyMCU would feed them, and the Baseline in force is rebuilt from the updates PyMCU would have sent
(a 10-count change, checked every 10 minutes). The DFM's contact test (signal above Baseline + 20)
is then compared under that baseline and under the fixed Starting baseline.

A run folder is one recording: a data/ folder with DFM<n>_<k>.csv files, and beside it the
flic_config.yaml pyflic uses. Its dfms: entries say which Wells are paired (6 chambers; the A Well
is the odd one with pi_direction: left, the even one with right) or single (12 chambers). The A Well
of a pair is the Sucrose Well in these recordings, the B Well the Yeast Well.

Writes a per-Well CSV to --out and a Markdown summary to --report. Needs numpy.

    python scripts/replay_baseline.py --out DIR --report docs/adaptive-baseline-replay.md RUN_FOLDER...
"""
import argparse
import csv
import datetime
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import BaselineTracker as BT  # noqa: E402

MARGIN = 20                 # The Threshold the replay tests contact against, above the Baseline
LONG_RUN_RECORDS = 1500     # A contact run longer than 5 minutes
P1_LOST_FRACTION = 0.01
REFERENCE_MINUTES = 31      # The reference resting level: rolling 10th percentile of the Floors
STEP_COUNTS = 20            # A reference change over 5 minutes bigger than this is a step
DRIFT_COUNTS = 10           # A step-free Well whose reference moves this much is drifting
SETTLE_MINUTES = 120        # P3 is judged after the first 2 hours
TRAINING_FLAG = 65536


def ReadConfig(path):
    """{DFM ID: (number of chambers, pi_direction)} from a flic_config.yaml, read line by line."""
    layout, current, chambers, inChambers, direction = {}, None, 0, False, "left"
    if not os.path.exists(path):
        return layout
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^- id:\s*(\d+)", line)
        if m:
            if current is not None:
                layout[current] = (chambers, direction)
            current, chambers, inChambers, direction = int(m.group(1)), 0, False, "left"
            continue
        if re.match(r"^\s+chambers:\s*$", line):
            inChambers = True
            continue
        m = re.match(r"^\s+pi_direction:\s*(\w+)", line)
        if m:
            direction = m.group(1).lower()
        if inChambers and re.match(r"^\s{4,}\d+:", line):
            chambers += 1
        elif inChambers and re.match(r"^\s{0,2}\S", line):
            inChambers = False
    if current is not None:
        layout[current] = (chambers, direction)
    return layout


def ReadThresholds(path):
    """{DFM ID: 12 thresholds of its first Interval} from a Program.txt (-1 or Off = Off)."""
    out, current = {}, None
    if not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8", errors="replace"):
        m = re.match(r"\*\*\*DFM (\d+)\*\*\*", line.strip())
        if m:
            current = int(m.group(1))
            continue
        if current is not None and current not in out and line.startswith("(") and ")" in line:
            tokens = [t.strip() for t in line.split(")", 1)[1].split(",")]
            values = []
            for t in tokens:
                if re.fullmatch(r"-?\d+", t):
                    values.append(int(t))
                elif t.lower() in ("on", "off"):
                    values.append(0 if t.lower() == "on" else -1)
                if len(values) == 12:
                    break
            if len(values) == 12:
                out[current] = values
    return out


def Roles(chambers, direction):
    if chambers == 12:
        return ["Single"] * 12
    roles = []
    for w in range(1, 13):
        isA = (w % 2 == 1) if direction == "left" else (w % 2 == 0)
        roles.append("Sucrose" if isA else "Yeast")
    return roles


def ReadWells(files):
    """(Sample numbers, n x 12 Well values) from a DFM's data files in order, training flag removed."""
    samples, wells = [], []
    for path in files:
        with open(path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            iSample = header.index("Sample")
            iWells = [header.index("W{}".format(w)) for w in range(1, 13)]
            for row in reader:
                if len(row) < len(header):
                    continue
                samples.append(int(row[iSample]))
                wells.append([int(row[i]) for i in iWells])
    values = np.array(wells, dtype=np.int64)
    values[values > 40000] -= TRAINING_FLAG
    return np.array(samples, dtype=np.int64), values


def StartingBaseline(values):
    """DFM.UpdateBaseline's running whole-number mean of the first 10 records."""
    baseline = [0] * 12
    for n in range(10):
        for w in range(12):
            baseline[w] = int((baseline[w] * n + int(values[n, w])) / (n + 1))
    return baseline


def Replay(samples, values, rate, cap):
    """The Baseline in force on every record, the update count, the cap events and the tracker."""
    start = StartingBaseline(values)
    tracker = BT.BaselineTracker(start, rate, cap)
    inForce = list(start)
    changes = [(0, list(inForce))]
    updates, caps = 0, []
    for i in range(10, len(samples)):
        for minute in tracker.AddRecord(int(samples[i]), values[i].tolist()):
            caps += minute.newlyCapped
            if minute.isCheck and tracker.NeedsUpdate(inForce):
                inForce = tracker.Rounded()
                updates += 1
                # In force from the next record; on a real bus about one read later.
                changes.append((i + 1, list(inForce)))
    perRecord = np.empty_like(values)
    bounds = [c[0] for c in changes] + [len(values)]
    for (first, baseline), end in zip(changes, bounds[1:]):
        perRecord[first:end] = baseline
    return start, perRecord, updates, caps, tracker


def Reference(samples, values):
    """Per-minute Floors and the reference resting level (their rolling 31-minute 10th percentile)."""
    minutes = (samples - 1) // BT.RECORDS_PER_MINUTE
    count = int(minutes.max()) + 1
    floors = np.full((count, 12), np.nan)
    # Records arrive in order, so a minute's rows are contiguous. A short minute stays NaN.
    edges = np.flatnonzero(np.diff(minutes)) + 1
    for block in np.split(np.arange(len(minutes)), edges):
        if len(block) >= BT.MIN_RECORDS_PER_MINUTE:
            ordered = np.sort(values[block], axis=0)
            floors[minutes[block[0]]] = ordered[int(BT.FLOOR_FRACTION * (len(block) - 1))]
    half = REFERENCE_MINUTES // 2
    reference = np.full_like(floors, np.nan)
    for m in range(count):
        window = floors[max(0, m - half):m + half + 1]
        if np.isfinite(window).any():
            reference[m] = np.nanpercentile(window, 10, axis=0)
    return minutes, reference


def Runs(mask):
    """(start, end) of each run of True, end exclusive."""
    edges = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)))


def AnalyseDFM(run, dfmID, files, layout, thresholds, rate, cap):
    samples, values = ReadWells(files)
    if len(samples) < 20:
        return []
    start, inForce, updates, caps, tracker = Replay(samples, values, rate, cap)
    minutes, reference = Reference(samples, values)
    refPerRecord = reference[minutes]
    chambers, direction = layout.get(dfmID, (12, "left"))
    roles = Roles(chambers, direction)
    hours = len(samples) / (BT.RECORDS_PER_MINUTE * 60)
    capped = {w: d for w, d in caps}
    rows = []
    for w in range(12):
        signal = values[:, w]
        fixed = signal > start[w] + MARGIN
        adaptive = signal > inForce[:, w] + MARGIN
        fixed[:10] = adaptive[:10] = False
        longRuns = [(a, b) for a, b in Runs(fixed) if b - a > LONG_RUN_RECORDS]
        lost = [float(np.mean(~adaptive[a:b])) for a, b in longRuns]
        ref = reference[:, w]
        finite = ref[np.isfinite(ref)]
        steps = np.abs(ref[5:] - ref[:-5]) if len(ref) > 5 else np.array([0.0])
        isStep = bool(np.nanmax(steps) > STEP_COUNTS) if np.isfinite(steps).any() else False
        movement = float(finite.max() - finite.min()) if len(finite) else 0.0
        kind = "step" if isStep else ("drift" if movement >= DRIFT_COUNTS else "flat")
        settled = np.arange(len(signal)) >= SETTLE_MINUTES * BT.RECORDS_PER_MINUTE
        gap = np.abs(inForce[:, w] - refPerRecord[:, w])[settled]
        gap = gap[np.isfinite(gap)]
        firstRef = finite[min(10, len(finite) - 1)] if len(finite) else start[w]
        rows.append(dict(
            Run=run, DFM=dfmID, Well=w + 1, Role=roles[w],
            Trigger=int(thresholds.get(dfmID, [-1] * 12)[w] > 0),
            Hours=round(hours, 2), Start=start[w], FinalInForce=int(inForce[-1, w]),
            FinalTracked=round(tracker.tracked[w], 1), Updates=updates,
            Capped=capped.get(w, 0), Kind=kind, ReferenceMovement=round(movement, 1),
            MaxGapAfter2h=round(float(gap.max()), 1) if len(gap) else "",
            LongRuns=len(longRuns), WorstLongRunLost=round(max(lost), 4) if lost else "",
            DifferingRecords=round(float(np.mean(fixed != adaptive)), 5),
            StartAboveFloor=int(start[w] - firstRef >= BT.UPDATE_STEP)))
    return rows


def FindDFMFiles(runFolder):
    data = os.path.join(runFolder, "data")
    groups = {}
    for name in os.listdir(data):
        m = re.fullmatch(r"DFM(\d+)_(\d+)\.csv", name)
        if m and int(m.group(1)) != 99:
            groups.setdefault(int(m.group(1)), []).append((int(m.group(2)), os.path.join(data, name)))
    return {d: [p for _, p in sorted(files)] for d, files in sorted(groups.items())}


def Quantiles(values):
    values = [v for v in values if v != ""]
    if not values:
        return "–"
    q = np.percentile(values, [50, 90, 100])
    return "{:g} / {:g} / {:g}".format(*(round(float(v), 2) for v in q))


def Report(rows, runs, rate, cap, path):
    byRole = lambda role: [r for r in rows if r["Role"] == role]
    sucrose, yeast = byRole("Sucrose"), byRole("Yeast")
    p1 = [r for r in sucrose if r["WorstLongRunLost"] != "" and r["WorstLongRunLost"] > P1_LOST_FRACTION]
    p2 = [r for r in sucrose if r["Capped"]]
    drifting = [r for r in yeast if r["Kind"] == "drift"]
    limit = BT.UPDATE_STEP + 2
    p3 = [r for r in drifting if r["MaxGapAfter2h"] != "" and r["MaxGapAfter2h"] > limit]
    dfms = {(r["Run"], r["DFM"]): r for r in rows}
    perDay = [r["Updates"] / (r["Hours"] / 24) for r in dfms.values() if r["Hours"] > 1]
    longRuns = sum(r["LongRuns"] for r in sucrose)

    def Verdict(failures):
        return "**pass**" if not failures else "**fail** ({})".format(len(failures))

    lines = [
        "# Adaptive baseline: replay of recorded data",
        "",
        "Written by `scripts/replay_baseline.py` on {}, for [adaptive-baseline-plan.md](adaptive-baseline-plan.md) stage S3. "
        "Every record of every DFM below went through `BaselineTracker` with `BaselineRatePerHour: {:g}` and "
        "`BaselineCapCounts: {}`, and the Baseline in force was rebuilt from the updates PyMCU would have sent. "
        "Contact is the DFM's test, signal above Baseline + {}, compared with the fixed Starting baseline.".format(
            datetime.date.today().isoformat(), rate, cap, MARGIN),
        "",
        "## Data",
        "",
        "{} recordings, {} DFMs, {} Wells:".format(len(runs), len(dfms), len(rows)),
        "",
    ]
    lines += ["- `{}`".format(r) for r in runs]
    lines += [
        "",
        "Sucrose Wells are the A Wells of paired chambers, Yeast Wells the B Wells, and Single Wells come from 12-chamber DFMs.",
        "",
        "## Pass criteria",
        "",
        "| | Criterion | Result |",
        "|---|---|---|",
        "| P1 | No contact run longer than 5 min on a Sucrose Well loses more than 1% of its records ({} runs on {} Wells) | {} |".format(
            longRuns, sum(1 for r in sucrose if r["LongRuns"]), Verdict(p1)),
        "| P2 | No Sucrose Well reaches the cap ({} Wells) | {} |".format(len(sucrose), Verdict(p2)),
        "| P3 | On drifting Yeast Wells, the Baseline in force stays within {} counts of the reference resting level after the first 2 h ({} Wells) | {} |".format(
            limit, len(drifting), Verdict(p3)),
        "",
        "The reference resting level is the rolling 31-minute 10th percentile of a Well's per-minute Floors. "
        "A Well is a *step* Well if its reference moves more than {} counts in 5 minutes, *drifting* if not and it moves "
        "{} counts or more over the recording, and *flat* otherwise.".format(STEP_COUNTS, DRIFT_COUNTS),
        "",
    ]
    for name, failures, field in (("P1", p1, "WorstLongRunLost"), ("P3", p3, "MaxGapAfter2h")):
        if failures:
            lines += ["{} failures, worst first:".format(name), "", "| Recording | DFM | Well | {} |".format(field), "|---|---|---|---|"]
            for r in sorted(failures, key=lambda r: -r[field])[:10]:
                lines.append("| `{}` | {} | {} | {} |".format(r["Run"], r["DFM"], r["Well"], r[field]))
            lines.append("")
    lines += [
        "## Reported",
        "",
        "Median / 90th percentile / maximum.",
        "",
        "| Measure | Value |",
        "|---|---|",
        "| Updates per DFM per day | {} |".format(Quantiles(perDay)),
        "| DFMs that sent no update | {} of {} |".format(sum(1 for r in dfms.values() if r["Updates"] == 0), len(dfms)),
    ]
    for role in ("Sucrose", "Yeast", "Single"):
        group = byRole(role)
        if not group:
            continue
        kinds = {k: sum(1 for r in group if r["Kind"] == k) for k in ("flat", "drift", "step")}
        lines += [
            "| {} Wells: flat / drifting / step | {} / {} / {} |".format(role, kinds["flat"], kinds["drift"], kinds["step"]),
            "| {} Wells capped (up / down) | {} / {} |".format(role, sum(1 for r in group if r["Capped"] == 1),
                                                            sum(1 for r in group if r["Capped"] == -1)),
            "| {} Wells: largest gap, Baseline in force to reference, after 2 h | {} |".format(role, Quantiles([r["MaxGapAfter2h"] for r in group])),
            "| {} Wells: share of records whose contact differs from the fixed baseline | {} |".format(role, Quantiles([r["DifferingRecords"] for r in group])),
            "| {} Wells whose Starting baseline was 10 or more above the floor | {} |".format(role, sum(r["StartAboveFloor"] for r in group)),
        ]
    lines += ["", "Per-Well results are in the CSV written beside the run (`--out`)."]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", help="Recording folders, each with a data/ folder")
    parser.add_argument("--out", default="replay_out", help="Folder for the per-Well CSV")
    parser.add_argument("--report", default=None, help="Markdown summary to write")
    parser.add_argument("--rate", type=float, default=BT.DEFAULT_RATE_PER_HOUR)
    parser.add_argument("--cap", type=int, default=BT.DEFAULT_CAP)
    parser.add_argument("--root", default=None, help="Shown in the report in place of this part of each path")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    rows, names = [], []
    for run in args.runs:
        name = os.path.relpath(run, args.root).replace("\\", "/") if args.root else run
        names.append(name)
        layout = ReadConfig(os.path.join(run, "flic_config.yaml"))
        thresholds = ReadThresholds(os.path.join(run, "data", "Program.txt"))
        for dfmID, files in FindDFMFiles(run).items():
            print("{} DFM {}".format(name, dfmID), flush=True)
            rows += AnalyseDFM(name, dfmID, files, layout, thresholds, args.rate, args.cap)
    with open(os.path.join(args.out, "replay_wells.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    if args.report:
        Report(rows, names, args.rate, args.cap, args.report)
    print("{} Wells; CSV in {}".format(len(rows), args.out))


if __name__ == "__main__":
    main()
