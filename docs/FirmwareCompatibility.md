# DFM firmware and what PyMCU can run on it

Last updated: 2026-10-14 (PyMCU 4.0.0)

PyMCU 4.0.0 drives every DFM firmware in the field: the 1.0.5 boards from 2021, both 2.0.0 builds, 2.0.1, 3.5.0 and 4.0.0. The DFM page shows each board's firmware. What a board can run depends on that firmware, so PyMCU checks a Program against every connected board when the file loads and again when Run Program is pressed, and names anything a board can't run. The Program file itself is described in [ProgramFormat.md](ProgramFormat.md); the protocol detail is in `FIRMWARE_VERSIONS.md` in the `DFMV3_V2` firmware repo.

## Which firmware runs what

| Paradigm type or setting | 1.0.5 | 2.0.0, 2.0.1 | 3.5.0 | 4.0.0 |
| --- | --- | --- | --- | --- |
| OpenLoop, ClosedLoop, FixedInterval | Runs | Runs | Runs | Runs |
| NonFeeding | **Refused** | Runs | Runs | Runs |
| ProgressiveRatio, FixedRatio, Acclimation | **Refused** | **Refused** | **Refused** | Runs |
| Times above 65,535 ms | **Refused** | Runs | Runs | Runs |
| EventGapMs | Ignored | Ignored | Ignored | Used |

Firmware before 4.0.0 runs its own version of the rules it supports, from the old decay, delay, max-time-on and pulse-width settings that PyMCU derives from each Paradigm. A 1.0.5 board doesn't know the non-feeding encoding and would run fixed interval instead, with no warning, and its times are two bytes, which is why PyMCU refuses those for that board rather than sending them. Old-style Interval lines are translated to Paradigms when the file loads; the old progressive-ratio and training encodings of firmware 2.0.0 are refused at load because they counted contact time rather than feeding bouts (ADR 0001).

## What PyMCU refuses, and where you see it

- **When the file loads.** A problem stops the load and names the line, for example `Line 12: PulseWidth must be shorter than one period (25 ms at 40 Hz)`, in a message box and on the Messages page.
- **After it loads.** A Compatibility Check box lists each connected board that can't run the Program, with the reason and the firmware it needs: `DFM 7 (firmware 1.0.5) can't run: the NonFeeding Paradigm type needs firmware 2.0.0` or `DFM 5 (firmware 3.5.0) can't run: the ProgressiveRatio Paradigm type needs firmware 4.0.0`.
- **Run Program.** The same check runs again, because a board may have been swapped, and the Program doesn't start while the list isn't empty.
- **While a Program runs.** If a board's firmware turns out to be older only then, the Interval it can't run isn't sent: the board keeps its last instruction and an Error message says why.

## What the DFM page shows for each firmware

- **Firmware.** `1.0.5` for a board that doesn't answer the version request (none of that generation do), otherwise what the board reports.
- **Error boxes.** Before firmware 3.5.0 a missed acknowledgement arrives on bit 1 (DFMV3 builds) or bit 0 (DFMV3_V2 builds), and the version string doesn't say which, so one box, No Ack, covers both. From 3.5.0, No Ack and Overflow are separate boxes. The other six boxes mean the same on every firmware. On a 1.0.5 board the version request itself raises P Type once; PyMCU clears that one report, so a ticked P Type box is a real unknown command.
- **Data file.** The same columns for every firmware. The Paradigm columns (Interval, Cycle, Paradigm, phases, Activations, requirements) are filled only for records from 4.0.0 boards. Firmware 2.0.0 and later flag a Well in training inside its value; PyMCU 4.0.0 drops the flag when it reads the record.

## Checking a build

`python -m unittest discover -s tests` on a PC runs the tests that pin the 41-byte (1.0.5), 47-byte (2.0.0 and later) and 63-byte (4.0.0) instruction frames, the version handling, the 56- and 127-byte records, the refusals above and the Program file checks. They need no hardware.
