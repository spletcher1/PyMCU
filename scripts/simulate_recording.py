#!/usr/bin/env python3
"""Simulates a PyMCU recording, for testing analysis software (pyflic) without flies.

Two DFMs (IDs 1 and 2), each with six two-well choice chambers (Linkage 1,1,2,2,...). Feeding on
a chamber's A well (1A, 2A ...) earns light for both its LEDs under a ProgressiveRatio Paradigm
(Arithmetic, FirstRequirement 1, Step 5, ActivationMs 500) that starts with 10 Acclimation
Activations; the B wells are Off. Two hours, firmware 4.0.0.

- Flies are simulated bout by bout and lick by lick. A fly's urge to feed from the A well is
  renewed by each Activation and fades while it works for the next, so as the Requirement grows
  each fly reaches its own breakpoint. Chambers differ: strong, medium and weak responders, and
  one fly per DFM that barely feeds.
- The DFM's signal is built ms by ms (resting level, noise, licks) and averaged over 128 scans,
  as the firmware does. Contact, Events, Acclimation and the progressive ratio follow the rules
  in docs/ProgramFormat.md, ms by ms.
- The resulting 127-byte firmware 4.0.0 records go through PyMCU's own record parser, DFM
  bookkeeping and data-file writer, so the files are what an MCU would write.

Beside the recording, a _truth folder lists every simulated bout and Activation and a summary
per Well, to check an analysis against.

Run from the PyMCU folder:
    .venv/bin/python scripts/simulate_recording.py [--out DIR] [--seed N] [--start "MM/DD/YYYY HH:MM:SS"]
"""
import argparse
import csv
import datetime
import math
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import DFM            # noqa: E402
import DFMGroup       # noqa: E402
import Enums          # noqa: E402
import Message        # noqa: E402
import MessagesList   # noqa: E402
import Program        # noqa: E402
import StatusPacket   # noqa: E402
from StatusPacket import Checksum32  # noqa: E402

DFM_IDS = (1, 2)
MINUTES = 120
RECORD_MS = 200
# The record-to-record time at which recording ends a little after the Program, as on the MCU.
EXTRA_RECORDS = 5
# The firmware compares the average of the last 128 scans (one about every 2.1 ms).
SCAN_WINDOW_MS = 269
THRESHOLD = 20
ACTIVATION_MS = 500
FIRST_REQUIREMENT = 1
STEP = 5
CAP = 65535
ACCLIMATION = 10
EVENT_GAP_MS = 100
PROGRESSIVE_RATIO = 4
# PyMCU sends the instruction once the baseline (the first 10 records) is done; it applies from
# this record.
APPLY_RECORD = 21
# No feeding in the first seconds, while the baseline is taken.
QUIET_MS = 10000
READ_RECORDS = 20
VOLTS_RAW = 777            # 5.01 V
WELL_NAMES = ["{}{}".format(c, s) for c in range(1, 7) for s in "AB"]

PROGRAM = """# Simulated recording: two hours of progressive ratio after 10 Acclimation Activations,
# in two-well choice chambers. Feeding on the A wells earns the light; the B wells are Off.
[General]
StartTime: {start}
ExpDurationMin: {minutes}
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Baseline: Yes

[Paradigm PR5]
Type: ProgressiveRatio
ActivationMs: {activation}
Series: Arithmetic
FirstRequirement: {first}
Step: {step}
Acclimation: {acclimation}

[DFM]
ID: 1
Interval: PR5, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, {minutes}

[DFM]
ID: 2
Interval: PR5, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, {minutes}
"""

# Fly kinds: A-well bouts per minute when just rewarded, how fast that urge fades without reward
# (minutes), what is left of it, B-well bouts per minute.
FLY_KINDS = {
    "strong":    dict(rateA=(5.0, 10.0), tau=(6.0, 25.0), floor=(0.03, 0.2), rateB=(0.4, 0.8)),
    "medium":    dict(rateA=(3.0, 5.0), tau=(6.0, 10.0), floor=(0.08, 0.15), rateB=(0.8, 1.5)),
    "weak":      dict(rateA=(1.0, 2.0), tau=(3.0, 6.0), floor=(0.04, 0.08), rateB=(1.5, 2.5)),
    "nonfeeder": dict(rateA=(0.02, 0.05), tau=(1.0, 2.0), floor=(0.5, 0.5), rateB=(0.02, 0.05)),
}
CHAMBER_KINDS = ["strong", "strong", "medium", "medium", "weak", "nonfeeder"]


class FakeMP:
    """Stands in for the bus: every command is acknowledged."""
    def __getattr__(self, name):
        return lambda *args: True


#region Flies
def Satiety(tMs):
    return 0.4 + 0.6 * math.exp(-tMs / (90 * 60000))


def MakeFly(rng, kind):
    k = FLY_KINDS[kind]
    return dict(kind=kind, rateA=rng.uniform(*k["rateA"]), tau=rng.uniform(*k["tau"]) * 60000,
                floor=rng.uniform(*k["floor"]), rateB=rng.uniform(*k["rateB"]),
                ampA=rng.uniform(250, 650), ampB=rng.uniform(250, 650))


def Bout(rng, start):
    """One feeding bout: licks of 25-110 ms about 150 ms apart, for 0.1-8 s."""
    duration = float(np.clip(rng.lognormal(math.log(1000), 0.7), 80, 8000))
    licks, t = [], start
    while t < start + duration or not licks:
        length = int(np.clip(rng.normal(60, 15), 25, 110))
        licks.append((int(t), length, rng.uniform(0.7, 1.3)))
        t += max(90, rng.normal(150, 25))
    end = licks[-1][0] + licks[-1][1]
    return dict(start=int(start), end=end, licks=licks)


def SimulateChamber(rng, fly, totalMs):
    """The fly's bouts on its A and B wells. The urge to use the A well is renewed by each
    Activation it earns, worked out roughly here (one Event per bout); the exact Activations come
    from the DFM's rules later."""
    bouts = []
    lastReward, rewards, progress, requirement = 0.0, 0, 0, FIRST_REQUIREMENT
    rewardEnd = -1.0
    maxRate = (fly["rateA"] + fly["rateB"]) / 60000
    t = float(QUIET_MS)
    while True:
        t += rng.exponential(1 / maxRate)
        if t >= totalMs - 2000:
            break
        rateA = fly["rateA"] * (fly["floor"] + (1 - fly["floor"]) * math.exp(-(t - lastReward) / fly["tau"])) * Satiety(t)
        rateB = fly["rateB"] * Satiety(t)
        u = rng.uniform(0, fly["rateA"] + fly["rateB"])
        if u >= rateA + rateB:
            continue
        well = "A" if u < rateA else "B"
        bout = Bout(rng, t)
        bout["well"] = well
        bouts.append(bout)
        if well == "A" and t >= rewardEnd:
            if rewards < ACCLIMATION:
                rewards += 1
                lastReward, rewardEnd = t, bout["end"] + ACTIVATION_MS
            else:
                progress += 1
                if progress >= requirement:
                    rewards += 1
                    progress = 0
                    requirement = min(CAP, FIRST_REQUIREMENT + STEP * (rewards - ACCLIMATION))
                    lastReward, rewardEnd = t, t + ACTIVATION_MS
        # The fly leaves the food for a moment between bouts.
        t = bout["end"] + rng.uniform(300, 1500)
    return bouts
#endregion


#region The DFM
def WellSignal(rng, resting, bouts, amplitude, totalMs):
    """Each ms's reading and the 128-scan average the DFM works from."""
    raw = np.full(totalMs, resting, dtype=np.float32)
    raw += rng.normal(0, 6, totalMs).astype(np.float32)
    for bout in bouts:
        for start, length, scale in bout["licks"]:
            raw[start:start + length] += amplitude * scale
    np.clip(raw, 0, 1023, out=raw)
    sums = np.cumsum(raw, dtype=np.float64)
    average = np.empty(totalMs, dtype=np.float32)
    average[SCAN_WINDOW_MS:] = (sums[SCAN_WINDOW_MS:] - sums[:-SCAN_WINDOW_MS]) / SCAN_WINDOW_MS
    average[:SCAN_WINDOW_MS] = sums[:SCAN_WINDOW_MS] / np.arange(1, SCAN_WINDOW_MS + 1)
    return average


def Baseline(values):
    """PyMCU's baseline (DFM.UpdateBaseline): a running integer average of the first 10 records."""
    baseline = 0
    for n, value in enumerate(values[:10]):
        baseline = int((baseline * n + value) / (n + 1))
    return baseline


def RunParadigm(contact, applyMs):
    """The DFM's rules for a triggering Well, ms by ms: Events (a rise above the Threshold, unless
    an Activation is running, ending after EVENT_GAP_MS below it), Acclimation (each of the first
    10 Events lights the LED during contact and for ActivationMs after; Main from the end of the
    10th), then the progressive ratio (Progress counts Events; meeting the Requirement starts an
    Activation of exactly ActivationMs, Progress goes back to 0 and the Requirement grows).
    Returns the lit ms, the state changes (ms, phase, activations, requirement, progress) and the
    Activations."""
    totalMs = len(contact)
    lit = np.zeros(totalMs, dtype=bool)
    phase, total, acclimation, main, progress, requirement = "A", 0, 0, 0, 0, FIRST_REQUIREMENT
    changes = [(applyMs, phase, total, requirement, progress)]
    activations = []
    running, holdEnd, runEnd = None, 0, 0
    inEvent, below, previous = False, 0, False
    contactAt = np.flatnonzero(contact)
    t = applyMs
    while t < totalMs:
        if not contact[t] and not previous and not inEvent and running is None:
            # Nothing happens until the next contact.
            j = np.searchsorted(contactAt, t)
            if j >= len(contactAt):
                break
            t = int(contactAt[j])
            continue
        c = bool(contact[t])
        if running == "Acclimation":
            if c:
                holdEnd = t + ACTIVATION_MS
            elif t >= holdEnd:
                running = None
                activations[-1]["end"] = t
                if acclimation >= ACCLIMATION:
                    phase = "M"
                    changes.append((t, phase, total, requirement, progress))
        elif running == "Main" and t >= runEnd:
            running = None
            activations[-1]["end"] = runEnd
        if c and not previous and not inEvent:
            inEvent = True
            if running is None:
                if phase == "A":
                    total += 1
                    acclimation += 1
                    running, holdEnd = "Acclimation", t + ACTIVATION_MS
                    activations.append(dict(kind="Acclimation", number=acclimation, start=t, met=""))
                else:
                    progress += 1
                    if progress >= requirement:
                        total += 1
                        main += 1
                        activations.append(dict(kind="Main", number=main, start=t, met=requirement))
                        progress = 0
                        requirement = min(CAP, FIRST_REQUIREMENT + STEP * main)
                        running, runEnd = "Main", t + ACTIVATION_MS
                changes.append((t, phase, total, requirement, progress))
        if c:
            below = 0
        elif inEvent:
            below += 1
            if below >= EVENT_GAP_MS:
                inEvent = False
        if running is not None:
            lit[t] = True
        previous = c
        t += 1
    if running is not None:
        activations[-1]["end"] = totalMs
    return lit, changes, activations


def AtRecordEnds(changes, ends):
    """Each record's (phase, activations, requirement, progress) from the state changes."""
    times = np.array([c[0] for c in changes])
    which = np.searchsorted(times, ends, side="right") - 1
    return [changes[i] if i >= 0 else None for i in which]
#endregion


def SimulateDFM(rng, dfmID, totalRecords):
    totalMs = totalRecords * RECORD_MS
    applyMs = (APPLY_RECORD - 1) * RECORD_MS
    ends = np.arange(1, totalRecords + 1) * RECORD_MS - 1
    kinds = list(CHAMBER_KINDS)
    rng.shuffle(kinds)
    wells = np.zeros((totalRecords, 12), dtype=np.int64)
    onMs = np.zeros((totalRecords, 12), dtype=np.int64)
    snapshot = np.zeros((totalRecords, 12), dtype=bool)
    state = [None] * 12
    baselines = [0] * 12
    truth = dict(flies=[], bouts=[], activations=[], summary=[])
    for chamber in range(6):
        a, b = 2 * chamber, 2 * chamber + 1
        fly = MakeFly(rng, kinds[chamber])
        bouts = SimulateChamber(rng, fly, totalMs)
        truth["flies"].append(dict(DFM=dfmID, Chamber=chamber + 1, WellA=a + 1, WellB=b + 1, Kind=fly["kind"],
                                   ABoutsPerMinRewarded=round(fly["rateA"], 2), UrgeFadeMinutes=round(fly["tau"] / 60000, 1),
                                   UrgeFloor=round(fly["floor"], 3), BBoutsPerMin=round(fly["rateB"], 2),
                                   LickAmplitudeA=round(fly["ampA"]), LickAmplitudeB=round(fly["ampB"])))
        for bout in bouts:
            well = a if bout["well"] == "A" else b
            truth["bouts"].append(dict(DFM=dfmID, Chamber=chamber + 1, Well=well + 1, WellName=WELL_NAMES[well],
                                       StartMs=bout["start"], DurationMs=bout["end"] - bout["start"], Licks=len(bout["licks"])))
        for well, resting, amplitude in ((a, rng.uniform(12, 40), fly["ampA"]), (b, rng.uniform(4, 25), fly["ampB"])):
            mine = [x for x in bouts if x["well"] == ("A" if well == a else "B")]
            average = WellSignal(rng, resting, mine, amplitude, totalMs)
            wells[:, well] = np.clip(np.rint(average[ends]), 0, 1023)
            baselines[well] = Baseline(wells[:, well])
            if well != a:
                continue
            # Only the A well triggers: its contact is above the Threshold measured from PyMCU's baseline.
            contact = average > baselines[well] + THRESHOLD
            contact[:applyMs] = False
            del average
            lit, changes, activations = RunParadigm(contact, applyMs)
            perRecord = lit.reshape(totalRecords, RECORD_MS).sum(axis=1)
            # Linkage: the chamber's B LED lights with its A LED.
            for w in (a, b):
                onMs[:, w] = perRecord
                snapshot[:, w] = lit[ends]
            state[a] = AtRecordEnds(changes, ends)
            for act in activations:
                truth["activations"].append(dict(DFM=dfmID, Well=a + 1, WellName=WELL_NAMES[a], Kind=act["kind"],
                                                 Number=act["number"], StartMs=act["start"], LitMs=act["end"] - act["start"],
                                                 RequirementMet=act["met"]))
            final = changes[-1]
            accl = [x for x in activations if x["kind"] == "Acclimation"]
            mains = [x for x in activations if x["kind"] == "Main"]
            truth["summary"].append(dict(
                DFM=dfmID, Chamber=chamber + 1, Well=a + 1, WellName=WELL_NAMES[a], Kind=fly["kind"],
                BoutsA=sum(1 for x in bouts if x["well"] == "A"), BoutsB=sum(1 for x in bouts if x["well"] == "B"),
                Activations=final[2], AcclimationActivations=len(accl),
                AcclimationEndMs=accl[-1]["end"] if len(accl) == ACCLIMATION else "",
                MainActivations=len(mains), Breakpoint=mains[-1]["met"] if mains else "",
                NextRequirement=final[3], ProgressAtEnd=final[4], LitMs=int(lit.sum())))
            del contact, lit
    return wells, onMs, snapshot, state, baselines, truth


def Records(dfmID, wells, onMs, snapshot, state, number, first, last):
    """The firmware 4.0.0 Status records first to last (from 1), as PacketManager.h lays them out."""
    out = b""
    for r in range(first, last + 1):
        i = r - 1
        applied = r >= APPLY_RECORD
        phaseBits, requirement, progress, activations = 0, [0] * 12, [0] * 12, [0] * 12
        if applied:
            for w in range(0, 12, 2):
                s = state[w][i]
                if s is not None:
                    _, phase, total, req, prog = s
                    phaseBits |= (1 << w) if phase == "A" else 0
                    activations[w], requirement[w], progress[w] = total & 0xFFFF, req, prog
        led = sum(1 << w for w in range(12) if snapshot[i, w])
        body = bytes([dfmID, 0]) + struct.pack(">HBH", number if applied else 0, PROGRESSIVE_RATIO if applied else 1, phaseBits)
        body += struct.pack(">12H", *(int(v) for v in wells[i])) + struct.pack(">HH", VOLTS_RAW, led)
        body += bytes(int(v) for v in onMs[i])
        body += struct.pack(">12H", *activations) + struct.pack(">12H", *requirement) + struct.pack(">12H", *progress)
        body += struct.pack(">I", r)
        out += body + Checksum32(body).to_bytes(4, "big")
    return out


def WriteCSV(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=os.path.expanduser("~/SimulatedFLICData"))
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--start", default="10/17/2026 13:00:00")
    args = parser.parse_args()
    rng = np.random.default_rng(args.seed)
    programStart = datetime.datetime.strptime(args.start, "%m/%d/%Y %H:%M:%S")
    totalRecords = MINUTES * 60 * 1000 // RECORD_MS + EXTRA_RECORDS

    messages = MessagesList.MessageList()
    DFM.DFM.DFM_message += messages.AddMessage
    Program.MCUProgram.Program_message += messages.AddMessage
    dfms = {}
    for ID in DFM_IDS:
        d = DFM.DFM(ID, Enums.DFMTYPE.PLETCHERV3, FakeMP())
        d.firmwareVersion, d.isVersionGetNeeded, d.DFMSubType = "4.0.0", False, Enums.DFMSUBTYPE.V2
        dfms[ID] = d
    program = Program.MCUProgram()
    text = PROGRAM.format(start=args.start, minutes=MINUTES, activation=ACTIVATION_MS, first=FIRST_REQUIREMENT,
                          step=STEP, acclimation=ACCLIMATION)
    if not program.LoadProgram(text.splitlines(True), dfms):
        sys.exit("Program didn't load: " + program.loadError)

    # As on the MCU: the recording's clock starts just after the Program's start time.
    startTime = programStart + datetime.timedelta(milliseconds=572)
    folder = os.path.join(args.out, "SIMMCU_" + programStart.strftime("%m_%d_%Y_%H_%M"))
    truthFolder = folder + "_truth"
    os.makedirs(folder, exist_ok=True)
    os.makedirs(truthFolder, exist_ok=True)
    with open(os.path.join(folder, "Program.txt"), "w") as f:
        f.write(str(program))
    messages.AddMessage(Message.Message(0, programStart + datetime.timedelta(milliseconds=1070), 0, "Recording started",
                                        Enums.MESSAGETYPE.ANNOTATION, -99))
    truth = dict(flies=[], bouts=[], activations=[], summary=[])
    lastTime = startTime
    for ID, d in dfms.items():
        print("DFM {}: simulating flies and the DFM...".format(ID))
        wells, onMs, snapshot, state, baselines, dfmTruth = SimulateDFM(rng, ID, totalRecords)
        for key in truth:
            truth[key] += dfmTruth[key]
        print("DFM {}: writing records through PyMCU...".format(ID))
        d.status = Enums.CURRENTSTATUS.RECORDING
        d.SetLinkage(program.GetLinkage(ID))
        d.BaselineDFM()
        instruction = program.theInstructionSets[ID].instructions[0]
        path = os.path.join(folder, d.outputFile)
        with open(path, "w") as f:
            f.write(DFMGroup.DATA_FILE_HEADER)
            for first in range(1, totalRecords + 1, READ_RECORDS):
                if first == APPLY_RECORD:
                    # The baseline is done: PyMCU sends the Interval, with thresholds measured from it.
                    if list(d.signalBaselines) != baselines:
                        sys.exit("Baselines differ: {} {}".format(list(d.signalBaselines), baselines))
                    d.UpdateInstruction(instruction, program.autoBaseline, 0, 1)
                last = min(totalRecords, first + READ_RECORDS - 1)
                data = Records(ID, wells, onMs, snapshot, state, d.instructionNumber, first, last)
                packets = []
                for n in range(last - first + 1):
                    sp = StatusPacket.StatusPacket(first + n, ID, Enums.DFMTYPE.PLETCHERV3)
                    sp.ProcessStatusPacket(data, startTime, n, StatusPacket.V4_PACKET_SIZE)
                    sp.secondsSinceReset = last * RECORD_MS / 1000 + 0.05
                    packets.append(sp)
                d.ProcessPackets(packets, True)
                lastTime = max(lastTime, packets[-1].packetTime)
                if d.theData.ActualSize() >= 1000:
                    lines, count = d.theData.PeekRecordsAsString()
                    f.write(lines)
                    d.theData.RemoveRecords(count)
            lines, count = d.theData.PeekRecordsAsString()
            f.write(lines)
            d.theData.RemoveRecords(count)
    messages.AddMessage(Message.Message(0, lastTime, 0, "Recording ended", Enums.MESSAGETYPE.ANNOTATION, -99))
    with open(os.path.join(folder, "Messages.csv"), "w") as f:
        f.write(messages.GetMessageStringForFile())

    for bout in truth["bouts"]:
        bout["StartTime"] = (startTime + datetime.timedelta(milliseconds=bout["StartMs"])).strftime("%H:%M:%S.%f")[:-3]
    for act in truth["activations"]:
        act["StartTime"] = (startTime + datetime.timedelta(milliseconds=act["StartMs"])).strftime("%H:%M:%S.%f")[:-3]
    WriteCSV(os.path.join(truthFolder, "Flies.csv"), truth["flies"])
    WriteCSV(os.path.join(truthFolder, "Bouts.csv"), truth["bouts"])
    WriteCSV(os.path.join(truthFolder, "Activations.csv"), truth["activations"])
    WriteCSV(os.path.join(truthFolder, "Summary.csv"), truth["summary"])
    with open(os.path.join(truthFolder, "README.txt"), "w") as f:
        f.write("Simulated with scripts/simulate_recording.py --seed {} --start \"{}\".\n"
                "Times in ms count from record 1's start ({}); record n covers ms (n-1)*200 to n*200.\n"
                "Flies.csv: each chamber's simulated fly. Bouts.csv: every feeding bout (lick train).\n"
                "Activations.csv: every Activation the DFM rules gave. Summary.csv: per triggering Well.\n"
                "Progress is taken to return to 0 when an Activation starts.\n".format(
                    args.seed, args.start, (startTime).strftime("%m/%d/%Y %H:%M:%S.%f")[:-3]))
    print("Recording: " + folder)
    print("Truth:     " + truthFolder)


if __name__ == "__main__":
    main()
