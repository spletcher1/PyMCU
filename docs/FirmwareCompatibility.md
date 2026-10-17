# DFM firmware and what PyMCU 3.5 can run on it

Last updated: 2026-10-16 (PyMCU 3.5.2)

PyMCU 3.5.2 drives every DFM that is not on firmware 4.0.0: the 1.0.5 boards from 2021, both 2.0.0 builds, 2.0.1, 3.5.0 and 3.5.1. The DFM page shows each board's firmware. What a board can run depends on that firmware, so PyMCU checks a Program against every connected board when the file loads and again when Run Program is pressed, and names anything a board would misread. This page lists the settings, which firmware runs what, and what the checks and the DFM page show. The protocol detail is in `FIRMWARE_VERSIONS.md` in the `DFMV3_V2` firmware repo.

## The opto settings

A Program file sets these in `[General]`, per DFM in a `[DFM]` section, or per Interval on a 19-number `Interval:` line (dark, 12 thresholds, OptoFrequency, OptoPW, OptoDecay, OptoDelay, MaxTimeOn, minutes). A 14-number line uses the section's values. A `[DFM]` section with `ID: All` applies to every connected DFM the file doesn't list by number; the `OptoTest` programs in `FLICPrograms` use it, one per rule in the table below (see [Testing the opto rules](#testing-the-opto-rules)).

| Setting | What it is | Accepted values |
| --- | --- | --- |
| OptoFrequency | LED pulse rate in Hz | 1 to 500. Firmware 2.0.0 and later also take `count × 512 + hertz` (count up to 127), which asks for `count` training Activations before progressive ratio starts: 1576 is three at 40 Hz. Only progressive ratio runs training, so PyMCU refuses a count with any other rule. DFM firmware 3.5.1 builds before the training-count fix give one Activation fewer than the count |
| OptoPW | Pulse width in ms | 1 to 1000, and shorter than one period (1000 / hertz). Firmware 2.0.0 and later also take `32768 + width` for non-feeding activation, which needs OptoDecay above 0 |
| OptoDecay | How long the LED stays on after contact ends. For fixed interval, non-feeding activation and progressive ratio, the on time (must be above 0 for the last two) | 0 to 4,294,967,295 ms (1.0.5 boards: up to 65,535) |
| OptoDelay | Fixed interval: the lockout after an Activation starts. With MaxTimeOn also above 0 on firmware 2.0.0 and later: progressive ratio, where it is the step in required contact (after the nth Activation, the next needs n × OptoDelay ms) | Same |
| MaxTimeOn | Cap on one on-period. In progressive ratio, the cap on the required contact instead | Same |

Thresholds: 0 is always on, anything above 1023 is off, otherwise the signal level (plus the baseline when Baseline is Yes) above which the Well counts as in contact. The baseline is the average of each Well's first 10 readings after the recording starts (about 2 s), and a DFM gets its instruction only once its baseline is done, so the LEDs stay off for the first few seconds of every run, open loop included. The data file always holds the raw signal, not the signal minus the baseline.

## Which firmware runs what

| Rule | How it is asked for | 1.0.5 | 2.0.0, 2.0.1 | 3.5.0, 3.5.1 | 4.0.0 |
| --- | --- | --- | --- | --- | --- |
| Open loop: always on, whatever the contact | thresholds 0 | Runs | Runs | Runs | Needs PyMCU 4.0.0 |
| Closed loop: on while above threshold, then OptoDecay ms more (0 = off at once), capped by MaxTimeOn (0 = no cap) | thresholds, OptoDecay, MaxTimeOn | Runs | Runs | Runs | Needs PyMCU 4.0.0 |
| Fixed interval: first contact lights for OptoDecay ms, then nothing new for OptoDelay ms | OptoDelay, MaxTimeOn 0 | Runs | Runs | Runs | Needs PyMCU 4.0.0 |
| Non-feeding activation: light after OptoDelay ms without contact, for OptoDecay ms | OptoPW 32768 + width | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |
| Progressive ratio by contact time: the first contact lights for OptoDecay ms; each later Activation needs OptoDelay ms more accumulated contact than the last, up to MaxTimeOn. Contact adds up across touches; only a new instruction restarts it | OptoDelay and MaxTimeOn both above 0, OptoDecay above 0 | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |
| Training count first, then progressive ratio: in training any contact lights the LED, holding keeps it on, and it stays on OptoDecay ms after release; training ends per Well when the last training Activation's OptoDecay runs out, then progressive ratio starts with no free Activation (the first needs OptoDelay ms of contact); a new instruction restarts training | OptoFrequency count × 512 + hertz, with progressive ratio | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |
| Times above 65,535 ms | any time setting | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |

A 1.0.5 board doesn't understand the three 2.0.0 encodings or the longer times. It would clamp or misread them and run a different rule with no warning, which is why PyMCU refuses them for that board rather than sending them.

## What PyMCU refuses, and where you see it

- **When the file loads.** Every setting is checked against the ranges above, line by line. A problem stops the load and names the line and the rule, in the status bar and on the Messages page, for example `Problem loading program: line 12: OptoPW 30 ms is not shorter than one period at 40 Hz (25.0 ms)`. The MCU then holds a simple program instead.
- **Settings that would run but do nothing useful** are refused at load too: progressive ratio or non-feeding activation with OptoDecay 0 (the firmware would light each Activation for 1 ms), for example `line 12: OptoDelay and MaxTimeOn both above 0 is progressive ratio, which needs OptoDecay above 0 for the light's on time`; and a training count with any rule but progressive ratio (the firmware ignores it), for example `line 12: OptoFrequency 1576 asks for 3 training Activations, which only run with progressive ratio`.
- **After it loads.** A Compatibility Check box lists each connected board that can't run the Program: a 1.0.5 board with the settings it would misread, such as `DFM 7 (firmware 1.0.5) can't run: non-feeding activation (OptoPW above 30000) needs firmware 2.0.0`, and any 4.0.0 board.
- **Run Program.** The same check runs again, because a board may have been swapped, and the Program doesn't start while the list isn't empty. Unplug the board, or change the Program.
- **While a Program runs.** If a board's firmware turns out to be 1.0.5 only then, the Interval it can't run isn't sent: the board keeps its last instruction and an Error message says why.

## Testing the opto rules

Each `OptoTest` program in `FLICPrograms` runs one rule on every connected DFM for 10 minutes, with thresholds of 50 above baseline (0 for open loop). The comment at the top of each file says what to do and what to see. Updates don't install `FLICPrograms`; copy the files to an MCU with **Move programs**. On DFM firmware 3.5.1 (with the non-feeding and training-count fixes) all six were checked on the bench on 2026-10-16:

| Program | Rule | Touch one Well and expect |
| --- | --- | --- |
| `OptoTest1_OpenLoop` | Open loop | All LEDs on a few seconds after the start, and staying on whatever you do |
| `OptoTest2_ClosedLoop` | Closed loop, OptoDecay 1000, MaxTimeOn 5000 | On while touched and 1 s after; a hold goes off after 5 s |
| `OptoTest3_FixedInterval` | Fixed interval, OptoDecay 2000, OptoDelay 10000 | 2 s on at a touch, then no new Activation for 10 s from its start |
| `OptoTest4_NonFeeding` | Non-feeding, OptoDecay 2000, OptoDelay 10000 | Untouched Wells: 10 s off, 2 s on, repeating. A touched Well stays dark and lights 10 s after the touch ends |
| `OptoTest5_ProgressiveRatio` | Progressive ratio, 2000 / 1000 / 5000 | Hold: 2 s on at once, then 2 s on after gaps of 1, 2, 3, 4, 5, 5 s |
| `OptoTest6_TrainingFirst` | 3 training Activations, then progressive ratio | 3 touches each light while held and 2 s after; then hold: 2 s on after 1, 2, 3, 4, 5, 5 s |

The DFM's own record of its LEDs is in the data file's `OptoCol1` (Wells 1 to 12 as bits 0 to 11) and `OptoCol2`. Records are 200 ms snapshots, so an on-period shorter than that may not show.

## What the DFM page shows for each firmware

- **Firmware.** `1.0.5` for a board that doesn't answer the version request (none of that generation do), otherwise what the board reports. A board on `4.0.0` or later gets one Error message, `DFM 7 runs firmware 4.0.0, which needs PyMCU 4.0.0 or later`, and is then neither instructed nor read.
- **Error boxes.** Before firmware 3.5.0 a missed acknowledgement arrives on bit 1 (DFMV3 builds) or bit 0 (DFMV3_V2 builds), and the version string doesn't say which, so one box, No Ack, covers both. From 3.5.0, No Ack and Overflow are separate boxes. The other six boxes mean the same on every firmware. On a 1.0.5 board the version request itself raises P Type once; PyMCU clears that one report, so a ticked P Type box is a real unknown command.
- **Data file.** The same 27 columns for every firmware. From 2.0.0 a Well value above 65,536 means the Well was in training during that record (the value minus 65,536 is the signal); the pyflic reader relies on this. PyMCU's thresholds and baselines ignore the flag.

## Checking a build

`python -m unittest discover -s tests` on a PC runs the tests that pin the 41-byte (1.0.5) and 47-byte (2.0.0 and later) instruction frames, the version handling, the 56-byte records, the refusals above and the program file checks. They need no hardware. The bench checklist for a release is in [v3-5-1-firmware-compat-plan.md](v3-5-1-firmware-compat-plan.md).
