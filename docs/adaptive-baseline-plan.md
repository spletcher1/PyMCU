# Adaptive baseline: Thresholds that follow slow drift

PyMCU only, for DFM firmware 4.0.0; firmware is unchanged. Decided in the design review of 1 November 2026. Stages S1–S5 were built on 1 November 2026 (PyMCU and pyflic `v4_Dev`, not committed); S6, the bench, is still to do. The S3 replay failed all three of its pass criteria; [adaptive-baseline-replay.md](adaptive-baseline-replay.md) has the numbers, and [Replay findings](#replay-findings) explains why. Terms are in [../CONTEXT.md](../CONTEXT.md), and the new ones are under [Terms](#terms). The data-file columns this changes are described in [DataFileColumns.md](DataFileColumns.md). The Program format is in [ProgramFormat.md](ProgramFormat.md).

This document is the whole specification. An implementer needs nothing else beyond PyMCU, pyflic and DFMV3_V2.

- [Goal](#goal)
- [Evidence](#evidence)
- [Decisions](#decisions)
- [Terms](#terms)
- [Rules](#rules)
- [Delivery stages](#delivery-stages)
- [PyMCU reference](#pymcu-reference)
- [pyflic reference](#pyflic-reference)
- [Tests](#tests)
- [Replay](#replay)
- [Bench checks](#bench-checks)
- [Numbers](#numbers)
- [Out of scope](#out-of-scope)

## Goal

With `Baseline: Yes`, PyMCU measures each Well's baseline once: the mean of the first 10 records of the recording (`DFM.UpdateBaseline`). Every Threshold it sends is that baseline plus the Program's margin, as an absolute signal level (`Instruction.SetOptoValueWell`). The DFM compares the 128-scan sum against Threshold × 128 every Tick (`LEDControl.c`, `StepWell`) and never knows a baseline exists. If a Well's resting signal drifts, its effective margin drifts with it, and nothing records that the baseline was used at all.

`Baseline: Adaptive` keeps the baseline current. PyMCU tracks each Well's resting level from the records it already receives. When the tracked value has moved far enough, PyMCU sends the running Interval's instruction again with new Thresholds, under a new instruction number and with the keep-state flag set, so no Well's Paradigm state is disturbed. Every row of the data file then says which baseline its Thresholds were built on.

The goal is only that a Threshold of 20 keeps meaning "20 above where this Well rests now". The adaptive baseline doesn't analyse feeding. pyflic still does that with its own running median.

## Evidence

Measured on 1 November 2026 on every real recording in `pyflic/test_data`: 9 recordings, 65 DFMs, 780 Wells. Eight are 24-hour 2025 recordings with 8 DFMs each (MBON02, MBON09 and PAM05 progressive ratio, two of each, and two MBa'b'ap closed loop) with Sucrose on the A Wells and Yeast on the B Wells. The ninth is a 10-hour MCU recording of one DFM without flies. There is no fly data yet from the MCU hardware with firmware 4.0.0; bench check B6 collects it. Stage S3 reproduces these numbers.

| Finding | Value |
|---|---|
| Sucrose Wells, change of the resting floor over 24 h | 13 counts at most; no Well ends more than 20 counts above its start |
| Sucrose Wells, fastest smooth drift | about 1–4 counts/h |
| Yeast Wells, smooth drift | up to about 10 counts/h over 2 h, 48 counts over 24 h |
| Yeast Wells, steps | 178 of 384 jump 70–1000 counts within 5 min; 20 never come back |
| MCU run without flies | 1 count in 10 h |
| Longest continuous contact on a lit Sucrose Well (Chrimson) | 76 min, 80–150 counts above the floor, light on throughout |
| The same with WCS controls under the same light | 6 min |
| Longest contact on an unlit Sucrose Well | 16 min |

Long contact is the larger effect, not drift. A plateau switches on and off sharply and comes back to its earlier level. It fills 100% of any window up to 60 min and 83% of a 2-hour window. pyflic's 3-minute running median absorbs it, which is probably why pyflic's light QC reports some plateaus as "drifting baseline or sustained contact".

That decides the estimator. The adaptive baseline must follow 1–4 counts/h but must not absorb a 76-minute plateau, and you can't tell a step from drift any sooner than the step lasts. So the tracker limits how fast the baseline may move, instead of choosing a window to average over.

## Decisions

| Question | Decision | Why |
|---|---|---|
| What it is for | The firmware's contact decisions and the live plot. Analysis stays with pyflic. | pyflic already removes drift offline. |
| Where it runs | PyMCU. It sends updated Thresholds in a new instruction with the keep-state flag. | No firmware release; works with every 4.0.0 board. Doing it in firmware would cost about 19 KB of the ring's RAM (780 → about 650 records) and change the Status record layout. Drift is slow, so 200 ms records are plenty. |
| Direction and limit | Both directions, capped at the starting baseline ± `BaselineCapCounts`, with one warning per Well at the cap | "Mild drift" only. A capped tracker can't run away. |
| How it is turned on | `Baseline: Adaptive` in `[General]`. `Yes` stays fixed. | Existing Programs and analyses are unchanged. |
| What is recorded | `Baseline1`–`Baseline12` on every row, written by PyMCU from its own record of each instruction it sent. Nothing new crosses the bus. Also written for `Baseline: Yes`. | The Threshold is this baseline plus the margin in `Program.txt`. pyflic's guess of the fixed baseline ("the first 10 s") is wrong today too. |
| Live plot | Subtracts the Baseline in force | A trace crossing the Threshold on screen means the light can respond. |
| Firmware older than 4.0.0 | Gets the Tracked baseline only with the instruction it receives anyway at an Interval or Cycle change; one notice per board | Any instruction resets its hold, lockout and training state and turns its LEDs off (3.5.x `SetLEDParams`), so a resend in the middle of an Interval would disturb the fly's light. |
| The 4.0.0 pulse restart | Accepted | Each instruction runs `SetOptoParameters`, which restarts the pulse counters: a Well lit at that moment has one pulse cycle cut short. This already happens at every Interval change. |
| When to send | Only when a Well's Tracked baseline is at least `D` = 10 counts from its Baseline in force, checked every `T` = 10 min | Only meaningful changes are sent; the floor's 2–5 count wobble never is. |
| `On` and `Off` Wells | Tracked and recorded like the others | Shows drift on control Wells, and a Well that later gets a numeric Threshold starts from a current baseline. |
| Long contact | Never absorbed on purpose. ClosedLoop's `MaxOnMs` is what limits lock-on. | The baseline follows the sensor, not the fly. |
| Estimator | Slow-moving floor tracker (see [Rules](#rules)) with the same rate limit up and down | It follows slow drift without lag and can't be dragged by a plateau. A long-window minimum or percentile lags hours behind upward drift. A mean frozen during contact stops updating once drift crosses the Threshold. |
| Starting baseline | The mean of the first 10 records, as today. Not corrected faster at the start. | Making sure no fly is on the food during those 2 s is the experimenter's job; the docs say so. |
| Settings | `BaselineRatePerHour` (default 5) and `BaselineCapCounts` (default 50) in `[General]`, refused unless `Baseline: Adaptive`. D and T are fixed in code. | Silently ignoring a setting would hide a typo in the design. |
| pyflic | Reads the columns, uses them in its emulated trigger, and splits "drifting baseline" from "sustained contact" in light QC | That's where the columns pay off. |

S2 records the reasoning in `docs/adr/0004-adaptive-baseline-in-pymcu.md`, written from this table and [Evidence](#evidence).

## Terms

S2 adds these to [../CONTEXT.md](../CONTEXT.md) under Data:

- **Baseline**: the resting signal a Well's Threshold is measured from. With `Baseline: Yes` it is the Starting baseline for the whole recording; with `Baseline: Adaptive` it follows the Tracked baseline; with `Baseline: No` it is 0. _Avoid_: offset, zero, resting level (pyflic's per-minute median).
- **Starting baseline**: the mean of a Well's first 10 records after the buffer reset that starts the recording.
- **Floor**: the 10th percentile of a Well's records in one minute of the recording. It ignores licks and bouts unless contact fills more than 90% of the minute.
- **Tracked baseline**: PyMCU's running estimate of the Baseline under `Baseline: Adaptive`. It moves toward each minute's Floor by at most the rate limit, within the cap.
- **Baseline in force**: the Baseline behind the Thresholds of the instruction a DFM is running. The `Baseline` columns and the live plot show it. It changes only when an instruction is sent.

## Rules

Each rule is testable on its own. Counts are signal units, 0–1023, as in `W1`–`W12`. R is `BaselineRatePerHour` and C is `BaselineCapCounts`.

1. **When it runs.** Only while a Program with `Baseline: Adaptive` is recording, and only after the Starting baseline is complete. The Tracked baseline starts equal to the Starting baseline, as a float.
2. **Minutes come from record indexes, not the clock.** Minute k holds the records whose `Index` (after the restart offset, as written to the file) is from 300(k−1)+1 to 300k. A minute is processed when the first record of a later minute arrives. A minute with fewer than 150 records (lost records, a restart) is skipped and leaves the Tracked baseline unchanged.
3. **Floor.** For each Well, sort the minute's values in ascending order. The Floor is the value at position ⌊0.1 × (n − 1)⌋, counting from 0. Values are the ones written to `W1`–`W12` (`StatusPacket` already drops the old training flag).
4. **Step.** For each Well, with `step = R / 60`: `tracked += max(−step, min(step, floor − tracked))`. The same limit applies up and down.
5. **Cap.** After the step, clamp to `[start − C, start + C]`. The first time a Well is clamped in a recording, post one warning: "DFM 3 Well 2A: baseline moved +50 from its start (12 → 62) and is held there. Check the Well." The Well stays clamped for as long as the step would take it past the limit.
6. **Check.** After processing minute k, if k is a multiple of 10 (T = 10 min), compare each Well's `round(tracked)` with its Baseline in force. If any Well differs by 10 or more (D), send an update. Otherwise send nothing.
7. **Update.** An update calls `instruct.SetBaseline([round(t) for t in tracked])` on the running Interval's instruction and sends it through `_SetInstruction` with the same Interval index and Cycle. That gives it a new instruction number, and since the Paradigm name is unchanged it goes out with the keep-state flag. All 12 Wells get their current value, not only those that moved 10 or more. Post one Messages.csv notice, not shown on screen, listing the Wells that moved by D or more: "DFM 3: baseline updated, 1A +11 (14 → 25), 4B −10 (40 → 30)."
8. **A new Interval or Cycle uses the Tracked baseline.** When `UpdateInstruction` starts a new Interval or Cycle under `Baseline: Adaptive`, it uses `round(tracked)` for every Well, with no D check. This is the only update older firmware gets.
9. **A resend of the same instruction keeps its baseline.** A NACK retry, the resend after a DFM restart, and `_CheckRunningInstruction`'s resend all re-send the current instruction number. They must carry the same Thresholds as when that number was first sent. So **the instruction's baseline is changed only inside rule 7 or rule 8, immediately before `_SetInstruction`**, never on its own.
10. **Firmware older than 4.0.0** gets no rule-7 updates. When it receives its first instruction, post one notice: "DFM 5 (firmware 3.5.2) gets its adaptive baseline only at Interval and Cycle changes."
11. **The record of what was in force.** `InstructionInfo` gains a `baseline` field: a tuple copy of the 12 baselines made in `_SetInstruction`, or `None` for an instruction that isn't from the Program (idle, all Off, Toggle Outputs) or when `Baseline: No`. Copy it, because the Program's instruction objects are reused for every Cycle and are changed by rules 7 and 8.

## Delivery stages

Each stage ends when its criterion holds. Only S6 needs real DFMs.

**S1 – Tracker module.** New module `BaselineTracker.py`, with no GUI, COMM or DFM imports. It holds the Starting baseline, takes records one at a time (index and 12 values), applies rules 2–6, and reports cap events and whether an update is due. Done when the [tracker tests](#tracker) pass.

**S2 – PyMCU integration.** The Program settings and refusals, rules 1 and 7–11 in `DFM.py` and `DFMGroup.py`, the `Baseline` columns, the messages, the live plot, the docs, the `CONTEXT.md` terms and ADR 0004. Done when `python -m unittest discover -s tests` passes, including the [integration tests](#integration).

**S3 – Replay.** `scripts/replay_baseline.py` runs `BaselineTracker` over the recordings in `pyflic/test_data` (see [Replay](#replay)). Done when its pass criteria hold and its report is saved next to this document as `adaptive-baseline-replay.md`.

**S4 – Simulator.** `scripts/simulate_recording.py` gains slow drift, a yeast-style step and a 60-minute plateau, and a run under `Baseline: Adaptive`, so the whole path is exercised without flies: tracker → update → instruction number → `Baseline` columns. Done when the simulated file has updates where the truth folder predicts them, `Baseline` columns that match them, and the plateau Well in contact throughout its plateau. (The simulator runs a progressive ratio, so its light isn't on throughout a plateau; contact is the property that matters.)

**S5 – pyflic.** See [pyflic reference](#pyflic-reference). Done when pyflic's tests pass, including new ones on an S4 file, and an older file without the columns gives the same results as before.

**S6 – Bench.** The [bench checks](#bench-checks), all passed, with the results noted at the top of this document.

## PyMCU reference

### Program file

`Program.py`:

- `_GENERAL_KEYS` gains `baselinerateperhour` and `baselinecapcounts`.
- `Baseline` accepts `Yes`, `No` or `Adaptive`, case-insensitively. `autoBaseline` stays a bool (true for Yes or Adaptive) so existing callers are unaffected, and a new `adaptiveBaseline` bool records Adaptive.
- `BaselineRatePerHour`: a number greater than 0, default 5. `BaselineCapCounts`: a whole number of at least 10, default 50, since a cap below D could never be sent. Anything else is a `ProgramError` on its line.
- After the whole file has been read, if either setting appears without `Baseline: Adaptive`, it is a `ProgramError`: "BaselineRatePerHour needs Baseline: Adaptive". The check runs after reading because the settings may come before `Baseline` in the file.
- `GetProgramDescription` (both branches) writes `Baseline: Adaptive` followed by `BaselineRatePerHour: 5` and `BaselineCapCounts: 50`, always with the values in force, so `Program.txt` records them.
- [ProgramFormat.md](ProgramFormat.md) describes the value and the two settings, says the experimenter must make sure no fly is on the food while the Starting baseline is taken, and adds an example.

### DFM.py

- `__init__` and `ResetBaseline`: add `self.tracker = None` and `self.baselineInForce = None`.
- `BaselineDFM()` is unchanged; it still collects the Starting baseline. When the 10th record completes it under Adaptive, create `BaselineTracker` from `signalBaselines`, R and C. `DFMGroup` passes R, C and the adaptive flag.
- `_AddPacket`: after `_AddParadigmState`, when recording and `self.tracker` exists, feed the record (`sp.recordIndex` after the offset, `sp.analogValues`). Act on its result: post cap warnings, and if an update is due on 4.0.0 firmware with a Program instruction running, apply rule 7.
- `UpdateInstruction`: under Adaptive, pass `round(tracked)` to `SetBaseline` instead of `signalBaselines` (rule 8). Under Yes it is unchanged.
- `_SetInstruction`: store the baseline copy in `InstructionInfo` (rule 11) and set `self.baselineInForce` for older firmware. `InstructionInfo` becomes `namedtuple("InstructionInfo", "index cycle instruction baseline")`. Update every place that builds one.
- `_AddParadigmState`: for 4.0.0 records, `sp.baseline = info.baseline if info else None`.
- Older firmware has no instruction number in its records. Record the baseline that an acknowledged instruction carried in `self.ackedBaseline`, and give records arriving after the acknowledgement that baseline. That is accurate to one read (4 s, or 0.33 s with fast updates), and for these boards the baseline changes only at Interval or Cycle starts.
- `GetLastAnalogData(True)` subtracts the Baseline in force: the last record's `sp.baseline` on 4.0.0, `ackedBaseline` on older firmware, and `signalBaselines` as now when neither exists.

### DFMGroup.py

- `StartRecording` passes the Program's adaptive flag, R and C to each DFM when it calls `BaselineDFM`.
- `DATA_FILE_HEADER` gains `StatusPacket.BASELINE_COLUMNS`. `ENVMON_FILE_HEADER` is unchanged.
- No other change. Rule-7 updates go through the DFM's existing `isInstructionUpdateNeeded` and `SendCommands` path, so retries, acknowledgements and `_CheckRunningInstruction` behave exactly as for an Interval change.

### StatusPacket.py

- `BASELINE_COLUMNS = ",".join("Baseline{}".format(w) for w in range(1, 13))`, written after `OnMs12`. A DFM file has 102 fields; the Environmental Monitor file keeps 27.
- `sp.baseline` defaults to `None`. `GetDataBufferPrintPacket` writes 12 integers, or 12 `NA` when it is `None`. It is `NA` in Interval 0 (`isBeforeProgram`), after the Program ends, with `Baseline: No`, and for idle or Toggle Outputs instructions.
- For older firmware, the 63 Paradigm columns stay `NA`, but the `Baseline` columns are filled by the acknowledgement rule above.

### Docs

- [DataFileColumns.md](DataFileColumns.md): the 12 columns, when they are `NA`, 102 fields per row (it says 90 now), and that Threshold = Baseline + the margin from `Program.txt` for numeric Thresholds.
- [UserGuide.md](UserGuide.md): what Adaptive does, in two paragraphs; the warning and notice texts; and a troubleshooting row: "Baseline held at its cap" means check the Well.
- [ProgramFormat.md](ProgramFormat.md): see [Program file](#program-file).

## pyflic reference

pyflic's own vocabulary is in `pyflic/CONTEXT.md` (Resting Level, Emulated Trigger, Explained Light).

- **Loading.** `Baseline1`–`Baseline12` are optional. Keep them out of `raw_df` the way `split_paradigm_columns` (`pyflic/base/paradigm_state.py`) keeps the Paradigm columns out, and expose them on the DFM, for example as `DFM.baseline_in_force`. Generation detection (`detect_generation`) works from `Phase1` and needs no change.
- **Emulated Trigger** (`pyflic/base/opto_qc.py`, `firmware_baseline`, `BASELINE_SECONDS`): when the columns are present, use the row's Baseline instead of the mean of the first 10 s. That also fixes the fixed-baseline case, where PyMCU really uses the first 10 records (2 s), and drops the "approximate" note.
- **Cause split** (`CAUSE_DRIFT` in `opto_qc.py`, used around its lines 1207 and 2051 and in `opto_light.py` around line 667): for files with the columns, report two causes.
  - **Sustained contact:** firmware contact or Activations with no pyflic activity, while the signal is at least the margin above the Baseline in force, and that Baseline is within D of the Well's own per-minute floor.
  - **Drifting baseline:** the same, while the Baseline in force is D or more below the floor, or the Well is at its cap.
  - Files without the columns keep the single label.
- **Light QC output:** per Well, how far the Baseline in force moved (first to last, maximum), how many updates there were, and whether the cap was reached, in `opto_light_qc.csv` and the report.
- **Docs:** `docs/firmware-4-data-in-pyflic.md`, the Emulated Trigger and Resting Level entries in `pyflic/CONTEXT.md`, and the CHANGELOG.

## Tests

### Tracker

In `tests/test_baseline_tracker.py`, using synthetic records only:

- A flat signal with ±3 counts of noise produces no updates in 24 h.
- A ramp of 4 counts/h is followed: after 6 h, `round(tracked)` is within 1 of the ramp. The first update comes when the ramp passes 10 and lands on the first multiple of 10 minutes after that.
- A 76-minute plateau 100 counts above a flat floor moves the Tracked baseline by at most 76/60 × R + 1 counts and causes no update. Afterwards the baseline comes back at R per hour.
- A drop of 30 counts is followed at R per hour, not at once.
- A step of +200 reaches the cap after C / R hours, posts exactly one cap event for that Well, and stays at start + C.
- A minute with 149 records changes nothing; one with 150 is used.
- Record indexes with a gap and with a restart offset fall into the right minutes.
- The Floor of a known 300-value minute equals the value at position ⌊0.1 × 299⌋ = 29.

### Integration

In `tests/test_dfm.py` and `tests/test_program.py`, with the fakes in `tests/support.py`:

- `Baseline: Adaptive` with both settings loads, and `Program.txt` shows all three lines. Either setting with `Baseline: Yes` or `No` is refused, with the line number. `BaselineCapCounts: 5` is refused.
- After an update, the DFM sends a new instruction number with the keep-state flag set and the Thresholds equal to the new baseline plus the margin. Records carrying the old number get the old `Baseline` values; records carrying the new number get the new ones.
- A same-number resend (`_CheckRunningInstruction`, the restart path) carries the same Thresholds as the original send, even when the Tracked baseline has moved since (rule 9).
- A new Interval under Adaptive carries `round(tracked)` with no D check (rule 8).
- A 3.5.2 board gets no mid-Interval updates, gets the Tracked baseline at the next Interval, and gets one notice. Its `Baseline` columns follow the acknowledgement.
- `Baseline: Yes` writes the Starting baseline in every row from Interval 1 on; `Baseline: No` writes `NA`. Interval 0 rows are `NA` in both.
- The data-file header has 102 fields and every row has 102.
- The cap warning appears once per Well, and the update notice is a Messages.csv-only notice.

## Replay

`scripts/replay_baseline.py <test_data folder>…` reads every `DFM<n>_*.csv` in a folder in file order, removes the old training flag (values above 40000 minus 65536), and for each Well:

1. Takes the Starting baseline as the mean of the first 10 rows, then feeds the rows to `BaselineTracker` with R = 5 and C = 50, using `Sample` as the index.
2. Rebuilds the Baseline in force from the updates rules 6 and 7 would have sent.
3. Compares contact (signal above Baseline in force + 20) with contact under the fixed Starting baseline + 20.

It writes a per-Well CSV and a Markdown summary. Sucrose and Yeast come from each folder's `project.yaml` (Well A is Sucrose; with `pi_direction: right` the even Well is A).

**Pass criteria:**

- **P1.** On Sucrose Wells, no continuous contact run longer than 5 min (under the fixed baseline) loses more than 1% of its records to the adaptive baseline.
- **P2.** No Sucrose Well reaches the cap.
- **P3.** On the 44 smoothly drifting Yeast Wells identified by the floor analysis, the Baseline in force stays within D + 2 counts of the 31-minute rolling 10th percentile of the per-minute Floor throughout, after the first 2 h.

**Reported, not judged:** updates per DFM per day; cap events by Well type; the largest gap between the Baseline in force and the Floor; and the share of records whose contact differs from the fixed baseline.

### Replay findings

The replay was run on 1 November 2026 over the 9 recordings ([adaptive-baseline-replay.md](adaptive-baseline-replay.md)).

**What went as intended.** Sucrose Wells' contact under the adaptive baseline differs from the fixed baseline's in none of the records for the median Well and at most 1% for any Well. 21 of 65 DFMs sent no update in a day, and the median DFM sent 2.

**All three criteria failed:**

- **P2: 3 Sucrose Wells reached the cap, all going down.**
  - Their Starting baselines were 59, 71 and 155, while their floors stayed flat all day at 9–21, so a fly was on the food during the first 2 s.
  - The baseline comes down at R and stops at the cap with a warning, as decided: starting clean is the experimenter's job.
  - Under a fixed baseline these thresholds would have been 40–135 counts too high all day.
  - The criterion needs to treat Wells whose Starting baseline is D or more above their floor separately.
- **P1: 1 Sucrose Well (MBa'b'ap Rep2, DFM 1, Well 5), 6 of 209 long runs.**
  - Its fly spent hours on the food. The minute's 10th percentile sat at 80–195 for whole half-hours.
  - The baseline therefore crept up at R to about 18, from a Starting baseline of 11 and a true floor of 13–16.
  - Contacts sitting 20–26 counts above the old Starting baseline then lost contact.
  - Part of the change corrects a Starting baseline about 4 counts too low. The rest is absorption at R, which R limits but can't prevent over hours.
- **P3: 21 of 26 drifting Yeast Wells.**
  - Yeast Wells sometimes drift faster than 5 counts an hour (up to about 10 an hour over 2 hours), and D holds back up to 9 counts, so the gap reached 14–27 counts.
  - Yeast Wells are `Off` in these Programs, so this affects only the `Baseline` columns, not the light.

**Sending only the Wells that moved D or more**, rather than all 12 at each update, cut per-Well baseline changes from 634 to 175 across all recordings. P1 still failed on the same Well: its worst run lost 93% instead of 63%, because the Well then jumps 10 counts at once.

**Open decisions:**

- Update all 12 Wells at each update, or only the Wells that moved D or more?
- Should R be lower than 5 for Sucrose triggers? Their measured drift is 1–4 counts an hour.
- How should P1–P3 be restated?

## Bench checks

On the MCU with 4.0.0 DFMs:

- **B1.** A Program with `Baseline: Adaptive` and `BaselineRatePerHour: 60` (fast, for the bench) runs 1 h on a DFM with a slowly changing test signal on one Well. Updates arrive at 10-minute boundaries, the DFM's records switch to each new instruction number, and the `Baseline` columns change on the first record that carries it.
- **B2.** During B1, a Well held in contact through an update keeps its light on, and its Activations and Requirement carry on across the update (keep-state). One pulse cycle cut short at the update is expected.
- **B3.** A DFM power-cycled after an update comes back with the latest instruction number and its Thresholds.
- **B4.** A 3.5.2 board on the same bus gets the notice and no mid-Interval updates.
- **B5.** pyflic (S5) loads the files, shows the movement of each Well's baseline, and its emulated trigger matches the firmware's Activations.
- **B6.** A 24-hour run with flies under `Baseline: Adaptive` and the defaults. Save its replay report (S3 script) beside `adaptive-baseline-replay.md` as the first drift measurement on the MCU hardware.

## Numbers

| Quantity | Value |
|---|---|
| R, `BaselineRatePerHour` | 5 counts/h by default, the same up and down; 0.083 counts per minute |
| C, `BaselineCapCounts` | 50 counts by default, at least 10; 10 h of steady movement at the default R |
| D | 10 counts, fixed |
| T | 10 minutes, fixed |
| Minute | 300 records; skipped below 150 |
| Floor | 10th percentile, position ⌊0.1 × (n − 1)⌋ |
| Fastest updates from rising drift | about one every 2 h per DFM at the default R (10 counts ÷ 5 counts/h) |
| A 76-minute plateau | moves the Tracked baseline about 6 counts; no update |
| Cost of an update | one 63-byte instruction and its acknowledgement |
| Data file | 102 fields per DFM row (was 90); Environmental Monitor 27 |

## Out of scope

- **Firmware.** A future release could make a repeated instruction leave the pulse train and the dark-mode state alone, by running `SetOptoParameters` and `SetDarkMode` in `ExecuteParadigmInstruction` (`src/UART2.c`) only when the frequency, pulse width or Dark byte changes. The dark-mode case matters because `SetDarkMode(1)` while already dark saves the indicator LEDs as all off. That would also remove the pulse cycle cut short at each update. It isn't needed for this work.
- Separate settings per DFM or per Interval.
- Absorbing long contact on purpose, or any judgement of behaviour.
- Fine mode ([v4-fine-mode-plan.md](v4-fine-mode-plan.md)). If both are built, a fine-mode recording's Fine blocks contain the same instruction numbers, so the `Baseline` columns work unchanged.
