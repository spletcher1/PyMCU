# v4 plan: explicit Paradigms between PyMCU and the DFM

This is the plan for DFM firmware 4.0.0 and the matching PyMCU. It records every decision made in the October 2026 design review. The terms used here are defined in [../CONTEXT.md](../CONTEXT.md). The reasons for the two less obvious choices are in [adr/0001](adr/0001-ratio-paradigms-count-events.md) and [adr/0002](adr/0002-status-records-carry-paradigm-state.md).

**Status (October 2026):** stages 1–4 are implemented on `v4_Dev` in both repos and pass their PC tests. The bench checks for each stage have not been run yet. Where the implementation settled a detail the plan left open, this document now describes the implementation.

## Goal

Today the DFM guesses the paradigm from which settings are zero, a pulse width above 30000 and bits hidden in the frequency. The data file can't say what a fly was doing, beyond a training flag added into the well values. After v4:

- Programs name their Paradigms and settings.
- The DFM receives the Paradigm type and settings explicitly.
- The data file reports each Well's Phase, Activations, Requirement, Progress and LED on-time, plus the Interval and Cycle.

## Branches and versions

- **Branches:** all work happens on new branches named `v4_Dev`, one in each repo (DFMV3_V2 and PyMCU), each branched from the repo's `v3_Dev` at the 3.5.0 release.
- **Firmware:** 3.5.0 remains the reliability release. The Paradigm redesign is firmware 4.0.0.
- **PyMCU** chooses the protocol from the DFM's firmware version:
  - **4.0.0 and later:** the new instruction and the new Status record.
  - **Older firmware:** today's instruction and record.
- **What PyMCU accepts or refuses:**
  - **Old Program files:** still load, except those using progressive ratio or acclimation bits, which are refused with a clear message.
  - **New Programs on older firmware:** PyMCU refuses to start a Program that needs a 4.0.0 feature on a DFM with older firmware, naming the DFM and the feature.
  - **Old PyMCU with 4.0.0 firmware:** not supported.

## The Paradigm model

### Paradigm types

Every Paradigm has `Frequency` (1–500 Hz) and `PulseWidth` (1 ms up to, but not including, one full period). The ratio types (and FixedInterval for `Acclimation`) also accept `EventGapMs` (default 100) and `Acclimation` (default 0); the rule table under Settings checks this. All times are in milliseconds.

| Type | Settings | Rule |
|---|---|---|
| OpenLoop | none | The LED is on, except at Wells set to Off |
| ClosedLoop | `HoldMs`, `MaxOnMs` (0 = no limit) | On during contact, and for `HoldMs` after contact ends. A continuous Activation is cut off after `MaxOnMs`; see confirmation C1. |
| FixedInterval | `ActivationMs`, `LockoutMs` | Contact starts an Activation of exactly `ActivationMs`. No new Activation can start until `LockoutMs` after the start of the previous one; see confirmation C2. |
| NonFeeding | `OnDelayMs`, `MaxOnMs` | Off during contact. Comes on `OnDelayMs` after contact ends and stays on for at most `MaxOnMs`. At the start of the Paradigm it comes on at once. |
| ProgressiveRatio | `ActivationMs`, `Series`, then `FirstRequirement` and `Step` (Arithmetic) or `Scale` and `Rate` (Exponential), and `Cap` | Meeting the Requirement starts an Activation of exactly `ActivationMs`. |
| FixedRatio | `ActivationMs`, `Ratio` | Every `Ratio`-th Event starts an Activation of exactly `ActivationMs`. The first one comes at Event `Ratio`. |

### Shared rules

- **Events:**
  - An Event starts when a Well's signal rises above its Threshold, unless an Activation is in progress.
  - It ends once the signal has stayed below the Threshold for `EventGapMs`.
  - Rises during an Activation don't count.
- **Requirement series:** k counts only Main-phase Activations since the Paradigm state began (see confirmation C4).
  - **Arithmetic:** Requirement_k = FirstRequirement + Step·(k−1), capped at `Cap`. FirstRequirement defaults to 1, so the first Event is rewarded.
  - **Exponential (Richardson–Roberts):** Requirement_k = round(Scale·e^(Rate·k) − Scale), capped at `Cap`. Scale defaults to 5 and Rate to 0.2, giving 1, 2, 4, 6, 9, 12, 15, 20, 25, 32, 40, 50, 62, 77, 95 …
  - `Cap` is at most 65,535.
- **Acclimation:**
  - Allowed only for ProgressiveRatio, FixedRatio and FixedInterval.
  - Acclimation N means each Well's first N Events each start a closed-loop Activation, using `ActivationMs` as the hold time.
  - That Well moves to the Main Phase when its Nth Activation ends.
  - N means N Activations the fly experiences; 2.0.x gave only N − 1.
  - Counted per Well.
- **Per-Well On and Off:** a threshold entry of `On` or `Off` overrides the Paradigm for that Well during the Interval.
- **Linkage:** unchanged. A Well's LED is lit whenever any Well in its group is lit. Each Well keeps its own Paradigm state.
- **When Paradigm state carries over:**
  - Paradigm state (Phase, Requirement, Progress, timers) carries across Interval changes while the Interval names the same Paradigm. That includes Repeating wraps and threshold-only changes.
  - It resets when the Paradigm changes.
  - PyMCU sets the instruction's keep-state flag when the Paradigm name is the same as the last one it sent. The DFM keeps the state only if the flag is set and the Type is also unchanged.
  - The Activation total per Well runs for the whole recording.
- **Recording start:**
  - All Paradigm state and Activation totals reset when recording starts. The DFM does this when it receives the buffer reset (0xFE) that PyMCU already sends at the start of recording, before the first instruction.
  - PyMCU sends no instruction until baselining has finished.

## Program file format

```
[General]
ExpDurationMin: 360
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Baseline: Yes

[Paradigm CL]
Type: ClosedLoop
Frequency: 40
PulseWidth: 8
HoldMs: 500

[Paradigm PR10]
Type: ProgressiveRatio
Frequency: 40
PulseWidth: 8
ActivationMs: 500
Series: Arithmetic
Step: 10
Cap: 200
Acclimation: 10

[DFM]
ID: 1
ProgramType: Linear
Interval: CL, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 30
Interval: PR10, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 330
```

- **Paradigm sections:** top-level `[Paradigm NAME]` sections only, usable by every DFM. Names are unique, and an Interval cannot override a setting.
- **Interval line:** Paradigm name, `Dark` or `Lit`, 12 thresholds (a number, `On` or `Off`), then minutes. Old 14- and 19-number lines still load, and a file may mix both styles.
- **Converting old lines:**
  - Dark 0/1 becomes `Lit`/`Dark`.
  - Threshold 0 becomes `On`, and -1 or above 1023 becomes `Off`.
  - The Paradigm is inferred from the Opto settings in force: OpenLoop, ClosedLoop, FixedInterval or NonFeeding.
  - Progressive ratio, and frequency above 500 (acclimation bits), are refused with instructions for rewriting.
- **Errors:** an unknown key, an unknown Paradigm, a setting the Type doesn't use, a value out of range, a malformed Interval line or a bad time each stop the load. The message shows the file, the line number and the problem, with no fallback to a default program. `StartTime` accepts `HH:MM` as well as `HH:MM:SS`.
- **Unchanged:** `[ENVMON]` and the Environmental Monitor's data.

## DFM protocol (firmware 4.0.0)

### Instruction, command 0xF7

Checksummed like today's instruction. Decoded layout, big-endian, as `ParseParadigmInstruction()` in DFMV3_V2 `src/LEDControl.c` reads it:

| Offset | Field | Bytes |
|---|---|---|
| 0 | ID, command | 1 + 1 |
| 2 | Instruction number | 2 |
| 4 | Type: 0 OpenLoop, 1 ClosedLoop, 2 FixedInterval, 3 NonFeeding, 4 ProgressiveRatio, 5 FixedRatio. Other codes, and a Series other than 0 or 1, are NACKed. | 1 |
| 5 | Flags: bit 0 = keep the Wells' Paradigm state (see "When Paradigm state carries over"). Other bits are 0. | 1 |
| 6 | Dark | 1 |
| 7 | Frequency, PulseWidth | 2 + 2 |
| 11 | EventGapMs | 2 |
| 13 | Acclimation N | 2 |
| 15 | Settings: 5 numbers whose meaning depends on the Type (below). Unused slots are 0. | 5 × 4 |
| 35 | Thresholds in the 0–1023 units of the data file's W1–W12, after baselining: 0xFFFF = Off, 0xFFFE = On | 12 × 2 |
| 59 | Checksum | 4 |

That's 63 bytes in total. The settings slots are:

| Type | Slot 1 | Slot 2 | Slot 3 | Slot 4 | Slot 5 |
|---|---|---|---|---|---|
| ClosedLoop | HoldMs | MaxOnMs | | | |
| FixedInterval | ActivationMs | LockoutMs | | | |
| NonFeeding | OnDelayMs | MaxOnMs | | | |
| ProgressiveRatio | ActivationMs | Series: 0 Arithmetic, 1 Exponential | FirstRequirement, or Scale × 1000 | Step, or Rate × 1000 | Cap (0 = 65,535) |
| FixedRatio | ActivationMs | Ratio | | | |

PyMCU's `tests/test_protocol.py` and the firmware's `tests/test_ledcontrol.c` check the same 63 example bytes, so the two sides can't drift apart.

- The DFM replies ACK or NACK as today, and repeats the instruction number in every Status record.
- Linkage stays a separate message (0xFB).
- 4.0.0 no longer accepts the old instruction (0xFD).

### Status record

| Offset | Field | Bytes |
|---|---|---|
| 0 | ID, error flags | 1 + 1 |
| 2 | Instruction number, Type | 2 + 1 |
| 5 | Phase bits: 1 = Acclimation, one per Well (bit 0 = Well 1). Wells set to On or Off are always 0. | 2 |
| 7 | Well signals: the average of the last 128 scans, which is what PyMCU records today | 12 × 2 |
| 31 | VoltsIn, LED snapshot | 2 + 2 |
| 35 | On-time in ms during the 200 ms, per Well | 12 × 1 |
| 47 | Activations per Well since the last buffer reset (wraps at 65,536) | 12 × 2 |
| 71 | Requirement per Well (ratio Types only, otherwise 0) | 12 × 2 |
| 95 | Progress per Well (ratio Types only, otherwise 0) | 12 × 2 |
| 119 | Index, checksum | 4 + 4 |

That's 127 bytes, against 56 today. The buffer holds 780 records, about 2.6 minutes of outage, and a reply carries at most 28 records. See confirmation C3.

The reliability protocol from 3.5.0 is unchanged: ACK, partial ACK, re-polling full replies, and overrun recovery.

## PyMCU changes

- **Program loading:**
  - A loader for the new format, plus conversion of old lines.
  - Loads either succeed or report an error; there is no silent fallback.
- **Instructions:**
  - The 0xF7 instruction for firmware 4.0.0 and later, and today's for older firmware.
  - The capability check before a Program starts.
  - Instruction numbers, each mapped to its Interval and Cycle.
- **Recording start:**
  - Reset Paradigm state when recording starts.
  - Send no instruction before baselining has finished.
- **Status records:**
  - A parser for the v4 record.
  - Activation totals are carried past 65,535 when the DFM's count wraps.
- **Data file:**
  - Every existing column stays where it is. W1–W12 no longer carry the +65536 flag, and OptoFreq/OptoPW/Dark come from the instruction that was active.
  - Appended: `Interval`, `Cycle`, `Paradigm`, `Phase1–12`, `Activations1–12`, `Requirement1–12`, `Progress1–12`, `OnMs1–12`.
  - Requirement and Progress are empty for Types other than the two ratio Types, and all new columns are empty for older firmware.
- **GUI:**
  - The DFM page's Status panel shows the Paradigm name, its Type and the Interval with its Cycle, in place of the raw Hz, ms and Optostate. The value column is widened from 45 to 80 pixels for this.
  - A "Well details" checkbox swaps the plot for a 12-Well table of Phase, Activations, Requirement, Progress and On ms.
  - Load errors appear as a message. Run Program refuses to start, with a message naming each DFM and feature, when a DFM's firmware can't run the Program.
- **Bug fixes:**
  - Constant Programs never sending an instruction.
  - `HH:MM` start times failing.
  - Unknown keys being ignored.

## Testing

- **Firmware:**
  - The Paradigm logic is in `src/LEDControl.c`, a C module with no hardware calls. It is compiled by XC32 for the DFM, and on a PC for unit tests that feed simulated Well signals 1 ms at a time.
  - `python tests/run_tests.py` builds and runs the tests with gcc, clang or cc if one is installed, and otherwise with Zig's C compiler (`pip install ziglang`).
  - Tests cover each Type, Events and the Event gap, Acclimation giving exactly N Activations, both Series (including the published exponential values), state carrying over between Intervals, linkage, wrap-around of the totals, the instruction bytes and the record layout.
- **PyMCU:** standard-library `unittest` tests in `tests/`, with the hardware modules stubbed; run `python -m unittest discover -s tests`. They cover:
  - Loading new and old files, including the refusals and error messages.
  - Encoding the instruction bytes.
  - Parsing the record.
  - Instruction numbers and the keep-state flag.
  - Carrying totals past a wrap, and resetting them at a buffer reset.
  - The data columns.
  - The check before a Program starts.
- **Bench:** each stage ends with a test on real DFMs before the next stage starts.

## Delivery stages

1. **Firmware, Paradigm module:** the module and its PC tests, plus the 0xF7 instruction. The Status record is unchanged in this stage. Bench: each Type behaves as specified on a DFM with a test signal.
2. **PyMCU, Programs and instructions:**
   - The new loader, its error messages and the conversion of old lines.
   - Sending the 0xF7 instruction, with version gating and the capability check.
   - Instruction numbers.
   - Reset at recording start, with no instruction before baselining.
   - The loader bug fixes.

   Bench: an example Program of each Type runs end to end.
3. **Firmware and PyMCU, records:**
   - The v4 Status record, with the new buffer depth and reply size.
   - PyMCU's parser and the carrying of totals past a wrap.
   - The data columns and the DFM page.

   Bench: a multi-DFM recording with no gaps, and Phase, Activations and Requirement matching what the LEDs did.
4. **Documentation:** rewrite the users' conventions document as `docs/ProgramFormat.md`. It covers every Type with a worked example and a "Converting old programs" section. `python docs/export_program_format.py` writes the plain-text copy, `docs/ProgramFormat.txt`; run it after each edit. The firmware README is updated and links to `CONTEXT.md`.

5. **Fine mode (firmware 4.1.0):** one DFM per bus reports every ADC scan and every decision change inside its Status record, which becomes a 2,304-byte block. Specified in [v4-fine-mode-plan.md](v4-fine-mode-plan.md); the reasoning is in [adr/0003](adr/0003-fine-data-over-the-bus.md). Starts only after stages 1–4 have passed their bench checks.

No 4.0.0 build is deployed before stage 3. Development builds report 4.0.0 from stage 1.

## Confirmations

These came up while writing the plan. Each was accepted as proposed and is implemented that way.

- **C1 – ClosedLoop `MaxOnMs`:** the agreed wording, "the timer restarts whenever the LED goes off", would let a cut-off LED come straight back on. Rule: the timer starts with each Activation. After a cut-off, the LED stays off until the current Event ends, and the next Event starts a fresh timer. This matches the old document's "any interruption in feeding resets the timer".
- **C2 – FixedInterval trigger:** the old document says the LED comes on when the Lockout ends "if the fly is still interacting". Rule: once the Lockout has passed, contact starts an Activation, including contact already in progress. A new Event is not required.
- **C3 – Record size:** the earlier estimate was about 100 bytes and about 1,000 records (3.3 minutes). The record is 127 bytes, with 780 records (about 2.6 minutes) and at most 28 records per reply. Dropping Requirement, which PyMCU can work out from the Type settings, would have given about 103 bytes and about 950 records (about 3.2 minutes), but would have made Requirement depend on PyMCU's arithmetic. 127 bytes was accepted.
- **C4 – Progressive-ratio counting:** k counts Main-phase Activations only, so Acclimation Activations don't move the Requirement along.
