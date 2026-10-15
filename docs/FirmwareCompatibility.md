# DFM firmware and what PyMCU 3.5 can run on it

Last updated: 2026-10-14 (PyMCU 3.5.1)

PyMCU 3.5.1 drives every DFM that is not on firmware 4.0.0: the 1.0.5 boards from 2021, both 2.0.0 builds, 2.0.1 and 3.5.0. The DFM page shows each board's firmware. What a board can run depends on that firmware, so PyMCU checks a Program against every connected board when the file loads and again when Run Program is pressed, and names anything a board would misread. This page lists the settings, which firmware runs what, and what the checks and the DFM page show. The protocol detail is in `FIRMWARE_VERSIONS.md` in the `DFMV3_V2` firmware repo.

## The opto settings

A Program file sets these in `[General]`, per DFM in a `[DFM]` section, or per Interval on a 19-number `Interval:` line (dark, 12 thresholds, OptoFrequency, OptoPW, OptoDecay, OptoDelay, MaxTimeOn, minutes). A 14-number line uses the section's values. A `[DFM]` section with `ID: All` applies to every connected DFM the file doesn't list by number; the `OptoTest` programs in `FLICPrograms` use it, one per rule in the table below.

| Setting | What it is | Accepted values |
| --- | --- | --- |
| OptoFrequency | LED pulse rate in Hz | 1 to 500. Firmware 2.0.0 and later also take `count × 512 + hertz`, which asks for `count` training Activations before the rule starts: 1576 is three at 40 Hz |
| OptoPW | Pulse width in ms | 1 to 1000, and shorter than one period (1000 / hertz). Firmware 2.0.0 and later also take `32768 + width` for non-feeding activation, which needs OptoDecay above 0 |
| OptoDecay | How long the LED stays on after contact ends. For fixed interval and non-feeding activation, the on time | 0 to 4,294,967,295 ms (1.0.5 boards: up to 65,535) |
| OptoDelay | Fixed interval: the lockout after an Activation starts. With MaxTimeOn also above 0 on firmware 2.0.0 and later: progressive ratio by contact time | Same |
| MaxTimeOn | Cap on one on-period | Same |

Thresholds: 0 is always on, anything above 1023 is off, otherwise the signal level (plus the baseline when Baseline is Yes) above which the Well counts as in contact.

## Which firmware runs what

| Rule | How it is asked for | 1.0.5 | 2.0.0, 2.0.1 | 3.5.0 | 4.0.0 |
| --- | --- | --- | --- | --- | --- |
| Open loop: on while above threshold | thresholds, no times | Runs | Runs | Runs | Needs PyMCU 4.0.0 |
| Closed loop: on while above threshold, then OptoDecay ms more, capped by MaxTimeOn | OptoDecay, MaxTimeOn | Runs | Runs | Runs | Needs PyMCU 4.0.0 |
| Fixed interval: first contact lights for OptoDecay ms, then nothing new for OptoDelay ms | OptoDelay, MaxTimeOn 0 | Runs | Runs | Runs | Needs PyMCU 4.0.0 |
| Non-feeding activation: light after OptoDelay ms without contact, for OptoDecay ms | OptoPW 32768 + width | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |
| Progressive ratio by contact time | OptoDelay and MaxTimeOn both above 0 | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |
| Training count first | OptoFrequency count × 512 + hertz | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |
| Times above 65,535 ms | any time setting | **Refused** | Runs | Runs | Needs PyMCU 4.0.0 |

A 1.0.5 board doesn't understand the three 2.0.0 encodings or the longer times. It would clamp or misread them and run a different rule with no warning, which is why PyMCU refuses them for that board rather than sending them.

## What PyMCU refuses, and where you see it

- **When the file loads.** Every setting is checked against the ranges above, line by line. A problem stops the load and names the line and the rule, in the status bar and on the Messages page, for example `Problem loading program: line 12: OptoPW 30 ms is not shorter than one period at 40 Hz (25.0 ms)`. The MCU then holds a simple program instead.
- **After it loads.** A Compatibility Check box lists each connected board that can't run the Program: a 1.0.5 board with the settings it would misread, such as `DFM 7 (firmware 1.0.5) can't run: non-feeding activation (OptoPW above 30000) needs firmware 2.0.0`, and any 4.0.0 board.
- **Run Program.** The same check runs again, because a board may have been swapped, and the Program doesn't start while the list isn't empty. Unplug the board, or change the Program.
- **While a Program runs.** If a board's firmware turns out to be 1.0.5 only then, the Interval it can't run isn't sent: the board keeps its last instruction and an Error message says why.

## What the DFM page shows for each firmware

- **Firmware.** `1.0.5` for a board that doesn't answer the version request (none of that generation do), otherwise what the board reports. A board on `4.0.0` or later gets one Error message, `DFM 7 runs firmware 4.0.0, which needs PyMCU 4.0.0 or later`, and is then neither instructed nor read.
- **Error boxes.** Before firmware 3.5.0 a missed acknowledgement arrives on bit 1 (DFMV3 builds) or bit 0 (DFMV3_V2 builds), and the version string doesn't say which, so one box, No Ack, covers both. From 3.5.0, No Ack and Overflow are separate boxes. The other six boxes mean the same on every firmware. On a 1.0.5 board the version request itself raises P Type once; PyMCU clears that one report, so a ticked P Type box is a real unknown command.
- **Data file.** The same 27 columns for every firmware. From 2.0.0 a Well value above 65,536 means the Well was in training during that record (the value minus 65,536 is the signal); the pyflic reader relies on this. PyMCU's thresholds and baselines ignore the flag.

## Checking a build

`python -m unittest discover -s tests` on a PC runs the tests that pin the 41-byte (1.0.5) and 47-byte (2.0.0 and later) instruction frames, the version handling, the 56-byte records, the refusals above and the program file checks. They need no hardware. The bench checklist for a release is in [v3-5-1-firmware-compat-plan.md](v3-5-1-firmware-compat-plan.md).
