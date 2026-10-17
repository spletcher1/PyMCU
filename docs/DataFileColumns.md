# DFM data file columns (PyMCU 4.0.0)

This is the reference for software that reads FLIC data files written by PyMCU 4.0.0 and later. It describes every column, with most detail on the 63 columns added in 4.0.0: what each holds, when it is missing and how that is written, which Programs make it meaningful, and how to use it in analysis and reports.

The terms (Paradigm, Interval, Cycle, Event, Activation, Phase, Requirement and so on) have exact meanings, defined in [../CONTEXT.md](../CONTEXT.md). The Paradigm rules are in [ProgramFormat.md](ProgramFormat.md).

- [The recording folder](#the-recording-folder)
- [Reading the file](#reading-the-file)
- [Original columns](#original-columns)
- [New columns](#new-columns)
- [Missing values](#missing-values)
- [Which Programs make which columns meaningful](#which-programs-make-which-columns-meaningful)
- [Deriving results](#deriving-results)
- [Telling file versions apart](#telling-file-versions-apart)
- [Checks worth running](#checks-worth-running)
- [Not yet confirmed](#not-yet-confirmed)

## The recording folder

Each recording is one folder, `FLICData/<MCU name>_<MM_DD_YYYY_HH_MM>/`, containing:

| File | Contents |
|---|---|
| `DFM<ID>_<n>.csv` | One per DFM. A new file (`_1`, `_2` …) is started every 12 hours of recording; concatenate them in order of `n`. Each file has its own header row. |
| `EnvMon_<n>.csv` | The Environmental Monitor (ID 99), if present. It keeps the old 27 columns and none of the new ones. |
| `Messages.csv` | Notices, warnings and errors during the recording: `DFM,Date,Time,Millisecond,Sample,Message,MsgType`. DFM 0 means the MCU itself. Annotations such as "Recording started" have `MsgType` `Unknown`. A message containing a comma is quoted. A message that repeats within 10 minutes is written once, ending "(repeated N more times, the last at HH:MM:SS)". Lost records are reported as "Lost N records (S s): Index A to B, from HH:MM:SS." |
| `Program.txt` | The Program that ran, as PyMCU understood it after loading. See below. |

### Program.txt

For a loaded Program it looks like this:

```
Start Time: 10/16/2026 23:34:00
End Time: 10/17/2026 05:34:00
Duration: 360 min
Default Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Default Program Type: Linear
Baseline: Yes

Paradigms:
Closed (ClosedLoop): Frequency 40 Hz, PulseWidth 8 ms, HoldMs 500 ms, MaxOnMs 2500 ms, EventGapMs 100 ms
PR10 (ProgressiveRatio): Frequency 40 Hz, PulseWidth 8 ms, ActivationMs 500 ms, Series Arithmetic, FirstRequirement 1, Step 10, Cap 200, EventGapMs 100 ms, Acclimation 10

***DFM 5***
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Program Type: Linear
(10/16/2026 23:34:00) Dark, Closed, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 30 min
(10/17/2026 00:04:00) Dark, PR10, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 330 min
```

- The `Paradigms:` block gives each Paradigm's name, its type in brackets and every setting, defaults included. This is the only place the Paradigm **type** and settings appear; the data file has only the name. Parse it to map `Paradigm` → type.
- Each `***DFM n***` block lists that DFM's Intervals in order. The k-th line is `Interval` k in the data file. Each line gives its scheduled start, `Dark` or `Lit`, the Paradigm name, the 12 thresholds (a number, `On` or `Off`) and the length.
- A recording started without loading a Program runs a simple built-in one, and its file starts with `***ALL DFM***`. It gives `Linkage:` and `Baseline:` at the top and one Interval, `Lit, Idle`, every Well `Off`, for the whole recording, with no `Paradigms:` block. `Idle` is ClosedLoop at 40 Hz and 8 ms.
- Old-format Programs get generated Paradigm names that describe them, for example `ClosedLoop-40Hz-8ms-Hold500-MaxOn0`.

## Reading the file

```python
import pandas as pd

df = pd.read_csv(path, dtype={"Interval": "Int64", "Cycle": "Int64", "Paradigm": "string",
                              **{f"Phase{w}": "string" for w in range(1, 13)},
                              **{f"{c}{w}": "Int64" for c in ("Activations", "Requirement", "Progress", "OnMs")
                                 for w in range(1, 13)}})
df["DateTime"] = pd.to_datetime(df["Date"] + " " + df["Time"], format="%m/%d/%Y %H:%M:%S") \
                 + pd.to_timedelta(df["MSec"], unit="ms")
```

- Missing values are the literal `NA`, which pandas' `read_csv` and R's `read.csv`/`readr::read_csv` treat as missing by default. Don't pass `keep_default_na=False` or `na_filter=False`.
- Without the nullable `Int64` dtype, any integer column with a missing value loads as float (1.0, 2.0 …).
- Every row has the same number of fields as the header: 90 for a DFM file, 27 for an Environmental Monitor file.
- In R, use `colClasses` or `readr` column types for the same reason. `Paradigm` is a string, and a Paradigm could in principle be named `NA`. PyMCU does not prevent this, so treat such a name as a known limitation, not a case to handle.

## Original columns

These 27 are unchanged in position and name from PyMCU 3.x. Each row is one Status record, covering 200 ms.

| Column | Type | Meaning |
|---|---|---|
| `Date`, `Time` | `MM/DD/YYYY`, `HH:MM:SS` | When the record was taken, on the MCU's clock. |
| `MSec` | float | Milliseconds past `Time`, with two decimals. The time is computed as recording start + `Index` × 200 ms, so consecutive records are exactly 200 ms apart. |
| `Sample` | int | Record number within the recording, from 1. It continues across the 12-hour file split. |
| `W1`–`W12` | int | Each Well's signal: the average of the last 128 Scans, 0–1023. Raw, **not** baseline-subtracted, even when `Baseline: Yes`. Wells 1–12 are 1A, 1B, 2A, 2B … 6A, 6B. A fly touching the food raises the signal. |
| `Temp`, `Humid`, `LUX` | float | °C, % relative humidity and lux from the Environmental Monitor at the time the record was read. 0 when there is no Environmental Monitor, since the DFM itself does not measure them. |
| `VoltsIn` | float | The DFM's supply voltage. |
| `Dark` | 0/1 | 1 when the Interval is `Dark` (the DFM's indicator LEDs off), 0 when `Lit`. It does not describe the OptoLid. |
| `OptoFreq` | int | LED pulse frequency (Hz) of the Paradigm in force. |
| `OptoPW` | int | LED pulse width (ms) of the Paradigm in force. |
| `OptoCol1` | int | Bit mask of which OptoLid LEDs were active at the instant the record was taken: bit 0 is Well 1, bit 11 is Well 12. It is a snapshot: a shorter on-period between snapshots won't appear. Use `OnMs` for exposure. |
| `OptoCol2` | int | Always 0 from firmware 4.0.0. |
| `Error` | int | The DFM's error flags. 0 means none. Errors are also explained in `Messages.csv`. |
| `Index` | int | The DFM's own record counter, from 1 at the start of recording. A gap means records were lost; they are never filled in or interpolated. If a DFM restarts on its own (a power dip, say), its counter starts again at 1; PyMCU then adds an offset so `Index` and the times carry on, and the jump in `Index` covers the time the DFM was restarting. `Messages.csv` reports the restart and the missing range. |

With firmware 4.0.0, `Dark`, `OptoFreq` and `OptoPW` are taken from the instruction the DFM reports it was running, not just from the Program's schedule. In baseline records from before any instruction, they are 0.

## New columns

These 63 follow `Index`, in this order: `Interval`, `Cycle`, `Paradigm`, then `Phase1`–`12`, `Activations1`–`12`, `Requirement1`–`12`, `Progress1`–`12`, `OnMs1`–`12`. The number after each name is the Well, 1–12, in the same order as `W1`–`W12`.

They come from firmware 4.0.0 boards only. For older firmware every one of them is `NA`.

### Interval

Which Interval of the DFM's Program was running, counting from 1 in the order of the DFM's Interval lines in `Program.txt`.

- `0`: the baseline, before the first Interval of the Program reached the DFM. PyMCU sends no instruction until it has measured each Well's resting signal (10 records), so every recording starts with a few seconds of Interval 0. In a test on 10/16/2026 it lasted 25 records (5 s). Exclude Interval 0 from analyses of the Program.
- `NA`: the DFM was running an instruction outside the Program after the Program had started, for example every LED Off after the Program ended.
- For a `Linear` Program that runs longer than its Intervals, the last Interval number repeats until the end.
- A recording started without loading a Program has `Interval` 1, `Cycle` 1 and `Paradigm` `Idle` after its baseline (see [Program.txt](#programtxt)).
- The value comes from the instruction number the DFM reports, so it changes on the first record the DFM ran under the new Interval, not at the scheduled time. Expect it to lag the schedule in `Program.txt` by up to a few hundred ms.

### Cycle

Which pass through the Program, from 1. What a Cycle is depends on the Program type, given per DFM in `Program.txt`:

| Program type | Cycle |
|---|---|
| `Linear` | Always 1 |
| `Constant` | Always 1 (only Interval 1 runs) |
| `Repeating` | 1 for the first pass through the Intervals, 2 for the second … |
| `Circadian` | 1 on the start day, 2 on the next day …; Interval 1 starts at midnight |

`NA` whenever `Interval` is 0 or `NA`. (Interval, Cycle) together identify one run of one Interval.

### Paradigm

The name of the Paradigm the DFM was running, as written in the Program's `[Paradigm NAME]` section. Look up its type and settings in `Program.txt`.

- `Idle` is PyMCU's own Paradigm: ClosedLoop at 40 Hz and 8 ms with every Well `Off`, so no LED lights. It is the single Interval of a recording started without a Program, and appears outside the Program too: in Interval 0 (when the DFM still has the idle instruction from before the recording) and after the Program ends.
- `NA` in Interval 0 when the DFM had not yet received any instruction PyMCU knows of.

### Phase1–Phase12

`A` while the Well is in Acclimation, `M` (Main) otherwise.

- Only Paradigms with `Acclimation: N` (N > 0) ever show `A`; those can only be FixedInterval, ProgressiveRatio and FixedRatio. Every other Paradigm is `M` throughout.
- A Well is `A` from the start of the Paradigm until its Nth Acclimation Activation ends, then `M` for good while that Paradigm continues. Each Well moves on separately.
- Wells set to `On` or `Off` are always `M`.
- Phase carries over into the next Interval only if that Interval names the same Paradigm (including a Repeating Program's new Cycle). A different Paradigm starts again in `A`, if it has Acclimation.
- Phase is reported in Interval 0 too, and is `M` there.

### Activations1–Activations12

The running total of Activations at the Well since recording started. An Activation is one LED on-period started by the Well's own Paradigm: a closed-loop contact plus its hold, a fixed-length Activation earned by FixedInterval or a ratio, an Acclimation Activation, and so on.

- It is **cumulative for the whole recording**: it never resets when the Interval, Cycle or Paradigm changes. Take differences to count Activations in a period.
- It never decreases. The DFM's own counter wraps at 65,536; PyMCU carries the total past that, so the file value keeps rising.
- It counts the Well's own Activations only. An LED lit by Linkage from another Well adds nothing to this Well's count. Use `OnMs` for light received.
- It counts Acclimation Activations as well as Main ones.
- It goes up in the record where the Activation's light starts (seen with ClosedLoop on 10/16/2026), so `diff()` > 0 marks Activation starts.
- Whether OpenLoop and `On` Wells add Activations is not yet confirmed (see [Not yet confirmed](#not-yet-confirmed)).

### Requirement1–Requirement12

Ratio Paradigms only (ProgressiveRatio and FixedRatio): the number of Events the Well must produce to earn its next Activation.

- FixedRatio: always the Paradigm's `Ratio`.
- ProgressiveRatio: the k-th Main-phase Activation needs, with Arithmetic Series, `FirstRequirement + Step × (k − 1)`, or with Exponential Series, `round(Scale × e^(Rate × k) − Scale)`, capped at `Cap`. Acclimation Activations don't advance k.
- `NA` for every other Paradigm type, in Interval 0, for Wells whose DFM reports 0 (see [Not yet confirmed](#not-yet-confirmed)) and for older firmware.
- It carries over between Intervals that name the same Paradigm, and starts again at the first Requirement when the Paradigm changes.

### Progress1–Progress12

Ratio Paradigms only: how many Events the Well has produced towards the current Requirement. When Progress reaches Requirement, an Activation starts. Missing exactly where `Requirement` is.

Events are feeding bouts, not milliseconds of contact or licks. An Event starts when the signal rises above the Well's Threshold, unless an Activation is in progress, and ends when the signal has stayed below the Threshold for `EventGapMs` (default 100 ms). So contact during an Activation doesn't count towards Progress.

### OnMs1–OnMs12

How many of the record's 200 milliseconds the Well's LED was active (pulsing at `OptoFreq` with `OptoPW` pulses), 0–200.

- It counts light from every cause: the Well's own Paradigm, an `On` threshold, and Linkage from another Well. It is the best measure of the light a fly actually received.
- "Active" means the LED was being driven in its pulse train during that time, not that it was emitting continuously. The emitting time is roughly `OnMs × OptoPW × OptoFreq / 1000`.
- Sum it over records for total exposure in ms.

## Missing values

Every missing value is written as `NA`. Nothing is left empty.

| Column | `NA` when | Other special value |
|---|---|---|
| `Interval` | The DFM ran an instruction outside the Program after the Program started (e.g. after it ended); firmware older than 4.0.0 | `0` for baseline records before the first Interval |
| `Cycle` | `Interval` is 0 or `NA`; firmware older than 4.0.0 | |
| `Paradigm` | Interval 0 before the DFM had an instruction PyMCU knows; firmware older than 4.0.0 | `Idle` outside the Program |
| `Phase`, `Activations`, `OnMs` | Firmware older than 4.0.0 only | |
| `Requirement`, `Progress` | Any Paradigm other than ProgressiveRatio or FixedRatio; the DFM reports a Requirement of 0; firmware older than 4.0.0 | |

`NA` in these columns means "doesn't apply", not "lost data". Lost records leave no row at all; detect them from gaps in `Index`.

## Which Programs make which columns meaningful

| Paradigm type | Phase | Activations | Requirement, Progress | OnMs | Notes |
|---|---|---|---|---|---|
| OpenLoop | always `M` | not confirmed (see below) | `NA` | yes: 200 for every `On` Well | Light doesn't depend on behaviour. |
| ClosedLoop | always `M` | yes: one per contact plus its hold | `NA` | yes | Light follows feeding. An Activation is cut off after `MaxOnMs`, and the LED stays off until that Event ends. |
| FixedInterval | `A`/`M` if `Acclimation` | yes: each is exactly `ActivationMs` in Main | `NA` | yes | A new Activation can't start until `LockoutMs` after the previous one started. |
| NonFeeding | always `M` | yes: each period the LED is lit | `NA` | yes | The LED is lit when the fly is **not** feeding: on at the start, off during contact, on again `OnDelayMs` after contact ends. |
| ProgressiveRatio | `A`/`M` if `Acclimation` | yes | yes | yes | Needs firmware 4.0.0. |
| FixedRatio | `A`/`M` if `Acclimation` | yes | yes (Requirement = `Ratio`) | yes | Needs firmware 4.0.0. |

- **Thresholds:** a Well with an `On` threshold is lit for the whole Interval whatever the Paradigm; a Well with `Off` is never lit by its own behaviour. An `Off` Well produces no Activations or Progress of its own. Read each Well's threshold for the Interval from `Program.txt`.
- **Linkage:** Wells with the same Linkage number light together. Each Well keeps its own Phase, Activations, Requirement and Progress, but `OnMs` and `OptoCol1` show the shared light. In a choice chamber (`Linkage: 1,1,2,2,…`) with one Well triggering and the other `Off`, the triggering Well has the Activations and both have the same `OnMs`. Control flies yoked by Linkage to a treatment Well have `OnMs` but no Activations.
- **Old-format Programs** become ClosedLoop, FixedInterval or NonFeeding Paradigms, so their files have Activations and OnMs but no Requirement or Progress.

## Deriving results

Feeding itself is analysed from `W1`–`W12` as before; the new columns describe the light.

- **Group by Interval:** use (`Interval`, `Cycle`) to split the recording into Program steps, and drop `Interval` 0 and `NA` for Program analyses. The Paradigm, its type and the Well thresholds for each Interval come from `Program.txt`.
- **Activations in a period:** the last `Activations` value in the period minus the last value before it. Within one Well, `diff()` gives the records where an Activation was counted.
- **Light exposure:** sum of `OnMs` over the period, per Well, in ms. Divide by the period length for the fraction of time lit.
- **Acclimation:** the time a Well finished Acclimation is the first record where its Phase changes from `A` to `M`. Wells that never reach `M` didn't complete Acclimation; report them.
- **Progressive-ratio breakpoint:** when a Main-phase Activation is counted, the Requirement in the record just before it is the one that was met. The breakpoint is the last Requirement met in the period, alongside the number of Main-phase Activations. The current `Progress` at the end shows how far the Well got towards the next one.
- **Events:** the file doesn't give a running total of Events. Under ratio Paradigms, Events can be counted from rises in `Progress` plus the Requirement met at each Activation (Progress returns to 0). For other Paradigms, Events have to be estimated from the Well signals.
- **Timing resolution:** records are 200 ms snapshots, so an Activation's start can only be placed within 200 ms. `OnMs` tells how much of a record was lit.

Reports should state, per DFM: the firmware version (shown on PyMCU's DFM page; it isn't written to the recording folder, but the new columns being `NA` throughout means firmware older than 4.0.0), the Program type, Linkage, each Paradigm with its type and settings, and each Interval's thresholds and length. All of this is in `Program.txt`.

## Telling file versions apart

| Header | Written by | New columns |
|---|---|---|
| 27 columns, ending `Index` | PyMCU 3.x | Absent. Wells in Acclimation under firmware 2.0.0 and later had 65,536 added to their `W` value. Subtract it if `W` > 1023. |
| 90 columns, ending `OnMs12`, with `NA` throughout the new columns | PyMCU 4.0.0 with firmware older than 4.0.0 | All `NA`. `W` values are clean. |
| 90 columns with values | PyMCU 4.0.0 with firmware 4.0.0 | Present. |

Files written by PyMCU 4.0.0 before 10/16/2026 23:30 (development builds only) wrote missing values as empty fields instead of `NA`, and baseline records with an empty `Interval` instead of 0. Treat empty and `NA` the same, and treat an empty `Interval` at the start of a recording as 0.

## Checks worth running

- Every row has the header's number of fields.
- `Index` rises by 1 each row; report any gaps, with their times and lengths.
- `Error` is 0; otherwise report the records and check `Messages.csv`.
- `Interval` starts at 0, then follows the Program's order. It never decreases within a Cycle, and `Cycle` never decreases.
- `Activations` never decreases, even across a DFM restart (the restart sets the Paradigm state back to its start, so `Phase` and `Requirement` can start again).
- `OnMs` is between 0 and 200, is 200 for `On` Wells, and is 0 for `Off` Wells that aren't linked to another Well.
- `Requirement` and `Progress` are non-`NA` only under ratio Paradigms, and `Progress` < `Requirement`.
- `Phase` goes from `A` to `M` at most once per Well per Paradigm run, and never back.

## Not yet confirmed

The firmware source isn't on the MCU, and these behaviours haven't yet been seen in a recording from a 4.0.0 board. Check them against real data before relying on them:

- Whether OpenLoop, and Wells set to `On`, count Activations (once per Interval, or never).
- Whether `Requirement` is reported (and so not `NA`) for `On`/`Off` Wells under a ratio Paradigm. PyMCU writes `NA` wherever the DFM reports 0. During Acclimation it is reported: the first Main-phase Requirement (seen with FixedRatio on 10/17/2026).
- Whether `Progress` returns to 0 when an Activation starts, or when it ends.

`FLICPrograms/OptoTest1_OpenLoop.txt`, `OptoTest5_ProgressiveRatio.txt` and `OptoTest6_TrainingFirst.txt` exercise all of these.
