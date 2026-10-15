# PyMCU 3.5.1 plan: one PyMCU for DFM firmware 1.0.5 through 3.5.0

Status: stages 1 to 3 implemented on PI5Dev on 2026-10-14 (three commits, see the git log); stage 4, the 3.5.1 release, waits for the bench checks. For branch `PI5Dev` (PyMCU 3.5.0 plus the Pi 4 and Touch Display 2 commits), which is what ships on the MCUs. The firmware facts come from `DFMV3_V2/FIRMWARE_VERSIONS.md`, which compares the three firmware generations and was checked against the source at each tag.

## Goal

PyMCU 3.5.1 drives every DFM that is not on firmware 4.0.0: 1.0.5 (the `DFMV3` boards from 2021), both 2.0.0 builds, 2.0.1 and 3.5.0. For each board it:

- sends the instruction in the format that board accepts, as today;
- refuses, before a Program starts, any setting that board would misread, naming the DFM, its firmware and the setting;
- labels the error bits the way that firmware uses them, as today;
- says plainly when a board needs PyMCU 4.0.0, instead of retrying forever;
- is covered by unit tests that run on a PC, so the oldest boards can't be broken by a later refactor without a failing test.

Nothing changes in the firmware, the data file or the Program file format. 4.0.0 boards stay the job of `v4_Dev`.

## Branches and versions

- **Branch:** all work on `PI5Dev`. `v4_Dev` branched from the same commit (`833c070`, the 3.5.0 release) and carries the Paradigm rewrite; three of the fixes below apply there too and are listed at the end.
- **Version:** 3.5.1, set in both `MainViewModel.py` (`APP_VERSION`) and `pyproject.toml`, then `uv lock`. Packaged with `CreateVersion.sh` and tagged `v3.5.1` as `docs/Packaging.md` describes. That page still says packages are built from `v3_Dev`; change it to `PI5Dev`.
- **What PyMCU accepts or refuses after 3.5.1:**
  - **1.0.5 boards:** OpenLoop-style (thresholds 0), closed-loop (OptoDecay, MaxTimeOn) and fixed-interval (OptoDelay with MaxTimeOn 0) settings, with every time at most 65,535 ms. Anything else is refused by name.
  - **2.0.0, 2.0.1 and 3.5.0 boards:** everything they run today, including the 2.0.0 encodings for non-feeding activation, progressive ratio and training.
  - **4.0.0 boards:** refused at connection with "needs PyMCU 4.0.0".

## What PI5Dev does today

Checked against the firmware source. Correct unless marked.

| Behavior (where) | 1.0.5 | 2.0.0 and 2.0.1 | 3.5.0 | 4.0.0 |
|---|---|---|---|---|
| Version read at connection and after any NACK (`DFMGroup`, `DFM.ReadFirmwareVersion`, `COMM.GetVersion`) | No reply in 30 ms, recorded as `1.0.5`; the probe sets 0x04 on the board (P2) | `2.0.0`, `2.0.1` | `3.5.0` | `4.0.0`, then treated as 2.x (P3) |
| Instruction format (`DFM.UsesV2Instructions`, `COMM.InstructionPayload`) | 41-byte 0xFD, 2-byte times | 47-byte 0xFD, 4-byte times | Same | 0xFD is NACKed; PyMCU re-probes every second forever (P3) |
| Old-style settings that only 2.0.0 understands: OptoPW above 30000, OptoFrequency above 500, OptoDelay and MaxTimeOn both above 0 | **Sent unchanged and misread (P1).** The board clamps the pulse width to one period, clamps the frequency, forces MaxTimeOn to 0 and runs fixed interval. Nothing warns | Run as 2.0.0 designed them | Same | |
| Times above 65,535 ms (`InstructionSet.IsVersion1_5Compatible`, `DFMGroup.CheckProgramCompatibility`) | Warning at load only; Run Program still starts and the value is truncated (P1) | Not needed | Not needed | |
| ACK, partial ACK (`DataGetter._Acknowledge`, `COMM.SupportsPartialAck`) | Full ACK right after each read; no partial ACK | Same | Partial ACK after a bad record | |
| Error labels (`DFMErrors.V3ErrorDisplay`) | Bits 0 and 1 together as No Ack | Same, right for both 2.0.0 builds | No Ack, Overflow | |
| Status records (`StatusPacket.ProcessStatusPacketPletcherV3`) | 56 bytes, 60 per reply | Same; the training flag stays in the data file as +65536, which pyflic relies on | Same | 127-byte records fail the size check |
| Baselining (`DFM.UpdateBaseline`) | Fine | Adds the +65536 training flag into the baseline if a Well is in training while baselining runs (P4) | Same | |
| Thresholds for 2.0.x and 3.5.0 on the 2.0.2 constant (`COMM.PARTIAL_ACK_FIRMWARE`, `DFMErrors`) | | Works because 3.5.0 sorts above 2.0.2, but 2.0.2 never shipped (P5) | | |
| Unit tests | None on this branch (P6) | | | |

## PyMCU changes

Each item names the behavior first, then where it goes.

1. **Refuse settings a board can't run (P1).**
   - `Instruction.DFMInstruction.FirmwareNeeded()` returns `None`, or a short reason naming the firmware it needs: "non-feeding activation (OptoPW above 30000) needs firmware 2.0.0", "training count (OptoFrequency above 500) needs firmware 2.0.0", "progressive ratio (OptoDelay and MaxTimeOn both above 0) needs firmware 2.0.0", "times above 65535 ms need firmware 2.0.0". The last replaces `IsVersion1_5Compatible()`.
   - `InstructionSet.FirmwareNeeded()` collects the reasons over its Intervals, in order, without repeats.
   - `DFMGroup.CheckProgramCompatibility()` returns a list of problem strings instead of a bool: one per DFM whose firmware major version is below 2 and whose InstructionSet needs 2.0.0, in the form "DFM 7 (firmware 1.0.5) can't run: non-feeding activation (OptoPW above 30000) needs firmware 2.0.0". It also lists every DFM on 4.0.0 or later (item 2). Versions are already read at connection, so the subtype is known by the time a Program loads.
   - `MainViewModel.LoadProgramClicked()` shows the list in the message box in place of today's single sentence. The Run Program handler calls the check again and refuses to start while the list is not empty, because a board can be swapped between load and run.
   - `DFM.CheckStatusV3()` does not send an instruction whose `FirmwareNeeded()` is set to a DFM whose major version is below 2. It posts one ERROR message naming the DFM and the reason, and leaves the Wells as they are. This is the last line of defense, reached only if the firmware changed after the check.

2. **Say when a board needs PyMCU 4.0.0 (P3).**
   - `DFM.ReadFirmwareVersion()` sets a new `isSupported` flag to False when the major version is 4 or more, posts one ERROR message "DFM 7 runs firmware 4.0.0, which needs PyMCU 4.0.0 or later", and `CheckStatusV3()` returns at once while the flag is False, so there is no NACK and re-probe loop. The DFM page keeps showing the firmware string.
   - `DFMGroup.CheckProgramCompatibility()` lists such boards so a Program can't start with them.
   - No attempt is made to read 127-byte records: a 3.5.x MCU does not drive a 4.0.0 board.

3. **Gate on 3.5.0, not 2.0.2 (P5).** `COMM.PARTIAL_ACK_FIRMWARE` becomes `(3, 5, 0)`; `DFMErrors.V3ErrorDisplay()` compares with the same constant instead of its own copy; `V3_ERROR_DISPLAY_BEFORE_2_0_2` becomes `V3_ERROR_DISPLAY_BEFORE_3_5_0`; the comments in `COMM.py`, `DFM.py` and `DFMErrors.py` that say 2.0.2 say 3.5.0. The comparison stays "at least".

4. **Baseline without the training flag (P4).** `DFM.UpdateBaseline()` uses the same flag-aware values as `GetLastAnalogData(True)`: a value above 40,000 has 65,536 subtracted before it enters the average. Anywhere else a raw Well value is compared with a threshold gets the same treatment; the data file keeps the raw value.

5. **One name for the oldest firmware.** The load-time message says "DFM firmware 1.0.5" instead of "Version 1.5 DFM". The identifiers `DFMSUBTYPE.V1_5`, `SendInstructionDFMV1_5`, `INSTRUCTION_V1_5` and `IsVersion1_5Compatible` are renamed to `V1_0_5` forms in the same change, since nothing was ever released as 1.5. This is mechanical and touches `Enums.py`, `COMM.py`, `DataGetter.py`, `DFM.py`, `DFMGroup.py`, `Instruction.py` and `InstructionSet.py`.

6. **Drop the probe's P Type error (P2).** When `GetVersion` returns `LEGACY_VERSION`, `DFM` masks bit 2 from the first record that arrives afterwards with it set, so a 1.0.5 board's page doesn't show P Type for the session because PyMCU asked a question it can't answer. The tooltip that explains this stays.

7. **Validate the old-style settings when a Program loads.** `Program.LoadProgram()` today converts every setting with `int()` and nothing else. Add range checks with line numbers in the message: OptoFrequency 1 to 500, or the 2.0.0 training form `count × 512 + hertz` with hertz 1 to 500; OptoPW 1 to 1000, or the 2.0.0 non-feeding form `32768 + width` with width 1 to 1000 and OptoDecay above 0; width shorter than one period; OptoDecay, OptoDelay, MaxTimeOn 0 to 4,294,967,295; 14 or 19 numbers on an Interval line. A failed check is reported as "Problem loading program: line 12: OptoPW must be ..." rather than the bare "Problem loading program".

8. **Document what runs where.** New `docs/FirmwareCompatibility.md` for 3.5.x users: the five settings, the 2.0.0 encodings for non-feeding, progressive ratio and training (with the formulas from item 7), a table of which firmware runs what, what the DFM page's Firmware field and error boxes show per firmware, and a pointer to `DFMV3_V2/FIRMWARE_VERSIONS.md` for the protocol detail. `docs/Updating.md` links to it. `docs/Packaging.md` names `PI5Dev`.

9. **Unit tests (P6).** A `tests/` folder run with `python -m unittest discover -s tests` on a PC. `tests/support.py` is copied from `v4_Dev` unchanged: it stubs `serial`, `smbus2`, `gpiozero` and the sensor libraries and supplies a small COBS implementation. The other files are written for this branch, not copied, because the `v4_Dev` tests are built on Paradigms:
   - `test_protocol.py`: a golden 41-byte and a golden 47-byte 0xFD frame for the same instruction, checked byte for byte; `LEGACY_VERSION` and `2.0.1` don't get partial ACKs and `3.5.0` does; a 56-byte record parses with its checksum, index and the training flag kept at +65536.
   - `test_dfm.py`: a DFM whose `GetVersion` times out is classified `1.0.5`, uses the 2-byte sender and the merged No Ack display; a DFM reporting `2.0.1` uses the 4-byte sender; a DFM reporting `4.0.0` sends nothing and posts the PyMCU 4.0.0 message; the probe's P Type bit is masked once; a baseline taken while a Well shows the training flag is unaffected.
   - `test_program.py`: Programs with 14- and 19-number Interval lines load; each refusal in item 7 names its line; `CheckProgramCompatibility` lists a 1.0.5 board for each 2.0.0-only setting and for a 70,000 ms OptoDecay, and lists nothing for the same Program on a 2.0.1 board.

## Testing

- **Unit:** the tests in item 9, run before each commit. They need no hardware.
- **Bench:** one session with one board of each generation on the same bus. Set distinct IDs with the 7-1 dial test in `DFMV3_V2/ID_DIALS.md` first.
  - [ ] Connect: the DFM page shows `1.0.5`, `2.0.x` and `3.5.0`, and the 1.0.5 board's P Type box stays clear.
  - [ ] A Program with closed-loop and fixed-interval Intervals runs on all three; each board ACKs its instruction at every Interval change and the LEDs behave the same.
  - [ ] A Program with OptoPW 32776 (non-feeding) loads with a refusal naming the 1.0.5 board, Run Program refuses while that board is connected, and with the board unplugged the 2.0.x and 3.5.0 LEDs come on only after OptoDelay ms of no contact.
  - [ ] The same for OptoFrequency 1576 (three training events at 40 Hz) and for OptoDelay 5000 with MaxTimeOn 20000, and for OptoDecay 70000.
  - [ ] A Program with a bad line (OptoPW 0, or 15 numbers on an Interval) is refused with the line number.
  - [ ] Record 10 minutes with the MCU paused for 30 s: no Skipped index or Repeated index on any board, No Ack on all three, Overflow on none.
  - [ ] Unplug the 3.5.0 board's bus for 6 minutes: Overflow shows, records resume with a gap and no repeats. The same on the 2.0.x board shows No Ack instead.
  - [ ] If a 4.0.0 board is available: connect it alone. The page shows `4.0.0`, one message says it needs PyMCU 4.0.0, and the MCU log shows no repeated "Instruction update NACKed".
  - [ ] Open each data file in pyflic: 27 columns, training values above 65,536 where expected.
- **Install:** the 3.5.1 package goes through the bench install checklist in `docs/Packaging.md` section 3.

## Delivery stages

1. **Checks and refusals:** items 1, 2 and 7, with the tests from item 9 that cover them and `tests/support.py`. Bench: the first five checks above, on a 1.0.5 board and a 2.0.x board.
2. **Cleanups:** items 3, 4, 5 and 6, with their tests. Bench: the recording and outage checks, on all three boards.
3. **Documentation:** item 8.
4. **Release 3.5.1:** version in both files, `uv lock`, commit, `CreateVersion.sh`, tag `v3.5.1`, bench install. No package is sent before stage 2 has passed its bench checks.

Each stage is one commit or a short series on `PI5Dev`, so a package can be built from any of them.

## Carry to v4_Dev

`v4_Dev` has the same gaps in its own shape; `DFMV3_V2/FIRMWARE_VERSIONS.md` lists them as G1 to G5. After stage 2:

- Item 1 becomes a `FirmwareNeeded()` reason for the NonFeeding Paradigm type on firmware below 2.0.0 (G1), and the "also runs on older firmware" sentence in `docs/ProgramFormat.md` is corrected.
- Items 3, 5 and 6 cherry-pick with small conflicts (G2, G4, G3).
- Item 9's 1.0.5 tests are added to `v4_Dev`'s `test_protocol.py` and `test_dfm.py` (G5).
- Item 4 is already handled there, because `v4_Dev` masks the training flag when it parses the record.

## Open questions

- **Q1. Refuse or warn on 1.0.5?** This plan refuses to start a Program that a connected 1.0.5 board would misread, as `v4_Dev` does for 4.0.0-only features. Today's behavior is a warning that is easy to miss. If the lab prefers to run the Program on the other boards and leave the 1.0.5 board idle, item 1's last point already does that; only the Run Program refusal would change to a confirmation.
- **Q2. Rename the `V1_5` identifiers now, or only the message?** The rename is mechanical but touches seven files; the message alone fixes what users see.
- **Q3. Does anyone still use the 2.0.0 training and progressive-ratio encodings on 2.0.x boards?** If not, item 7 can refuse OptoFrequency above 500 and the OptoDelay-with-MaxTimeOn combination outright, as `v4_Dev` does, and item 8 need not document them.
- **Q4. Which build is on the oldest boards?** `v1.0.5`, `V1_0_6` and `master` of `DFMV3` differ only in ID-dial settings, so the plan holds for all three, but the bench test should use the build that is actually deployed.
