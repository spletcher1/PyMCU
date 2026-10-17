# Writing MCU Programs

A Program tells the MCU how long to record and what each DFM's optogenetic LEDs should do. This guide is for PyMCU with DFM firmware 4.0.0. It replaces "Stand Alone MCU Programming Conventions" (the draft for version 2.0). Programs written for that document still load, and [Converting old programs](#converting-old-programs) explains what happens to them.

Questions and suggestions: Scott Pletcher (spletch@umich.edu).

- [A first Program](#a-first-program)
- [Getting a Program onto the MCU](#getting-a-program-onto-the-mcu)
- [How a Program file is laid out](#how-a-program-file-is-laid-out)
- [General settings](#general-settings)
- [Paradigms](#paradigms)
- [The six Paradigm types](#the-six-paradigm-types)
- [DFM sections and Intervals](#dfm-sections-and-intervals)
- [The Environmental Monitor](#the-environmental-monitor)
- [Which DFMs can run what](#which-dfms-can-run-what)
- [What the data file records](#what-the-data-file-records)
- [Converting old programs](#converting-old-programs)

## A first Program

```
# Six hours. DFM 1: closed loop. DFM 2: 30 minutes of closed loop, then progressive ratio.
[General]
ExpDurationMin: 360
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Baseline: Yes

[Paradigm Closed]
Type: ClosedLoop
HoldMs: 500

[Paradigm PR]
Type: ProgressiveRatio
ActivationMs: 500
Step: 5

[DFM]
ID: 1
Interval: Closed, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 360

[DFM]
ID: 2
Interval: Closed, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 30
Interval: PR, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 330
```

- The `[Paradigm]` sections name two rules for lighting the LEDs, and the `[DFM]` sections say which rule each DFM follows, and when.
- In every chamber, only the A well (left) can trigger the light. A signal above 20 counts as contact. The B wells are `Off`, but linkage lights both LEDs in a chamber together.
- `Dark` turns off the indicator LEDs on top of the DFM board.

## Getting a Program onto the MCU

1. Write the Program as a plain text file with the extension `.txt`, for example in Notepad.
2. Put it in a folder called `FLICPrograms` (case sensitive) at the top level of a USB stick.
3. On the MCU, press Programs → Custom → Get (USB). Every `.txt` file in that folder is copied to the MCU.
4. Choose the file and press Load.

If anything in the file is wrong, nothing is loaded, and the MCU shows a message giving the line number and the problem. For example:

```
Line 14: ClosedLoop Paradigms don't use Step
Line 22: Thresholds are On, Off or a signal level from 1 to 1023, not '0'
Line 9: Unknown setting 'Colour'
```

The MCU also checks that every DFM it has found can run the Program. If one can't, it says which DFM and why, and Run Program won't start. See [Which DFMs can run what](#which-dfms-can-run-what).

## How a Program file is laid out

- Each line is a section heading in square brackets, a setting written `Name: value`, a comment starting with `#`, or blank.
- Setting names, Paradigm names and words such as `Dark`, `On` and `Yes` can be in any case. Spaces around values don't matter.
- The sections are:
  - `[General]`: the experiment as a whole. Put it first.
  - `[Paradigm NAME]`: one named rule for lighting the LEDs. A Program can have any number.
  - `[DFM]`: one per DFM, saying which Paradigm it follows, when, and at which thresholds.
  - `[ENVMON]`: the Environmental Monitor, if you use its relays and outputs.
- An unknown section or setting, a setting in the wrong section, or a value out of range stops the load with a message. Misspellings are never silently ignored.

## General settings

| Setting | Meaning | Default |
|---|---|---|
| `StartTime` | When recording starts: `HH:MM`, `HH:MM:SS` (24-hour clock, today) or `MM/DD/YYYY HH:MM:SS`. The Program screen can also change it. | The start of the next minute after loading |
| `ExpDurationMin` | How long recording lasts, in minutes. Always set it. | 1 |
| `ProgramType` | How each DFM steps through its Intervals: `Linear`, `Repeating`, `Circadian` or `Constant`. A `[DFM]` section can override it. See [Program types](#program-types). | `Linear` |
| `Linkage` | 12 numbers, one per Well. Wells with the same number light together. A `[DFM]` section can override it. See [Linkage](#linkage). | `1,2,3,4,5,6,7,8,9,10,11,12` (no linkage) |
| `Baseline` | `Yes` measures each Well's resting signal over its first 10 readings after recording starts (a few seconds), and thresholds are then measured from it. A DFM starts its first Interval only once that is done, so its LEDs stay off for those seconds, even in an OpenLoop Interval. `No` uses the raw signal. | `Yes` |

`[General]` also accepts the old `OptoFrequency`, `OptoPW`, `OptoDecay`, `OptoDelay` and `MaxTimeOn` settings, but only for old-style Interval lines. New Programs set these in Paradigms instead.

## Paradigms

A Paradigm is a named rule for when a Well's LED turns on, together with the light settings. Write one `[Paradigm NAME]` section for each, and use its name in Interval lines. Several DFMs, and several Intervals, can use the same Paradigm.

```
[Paradigm Interval1Min]
Type: FixedInterval
Frequency: 40
PulseWidth: 8
ActivationMs: 1000
LockoutMs: 60000
```

- **Names** start with a letter, and may also contain digits, underscores, hyphens and full stops, but no spaces. Each name is used once. `Dark`, `Lit`, `On` and `Off` can't be names.
- **`Type`** is required: one of the six types below.
- **Every type** takes:
  - `Frequency`: LED pulses per second, 1–500. Default 40.
  - `PulseWidth`: how long each pulse is on, in ms. It must be shorter than one period (1000 ÷ Frequency ms). Default 8.
- **Other settings** depend on the type. A setting the type doesn't use is an error, so a typo can't go unnoticed. All times are in milliseconds.

### Contact, Events and Activations

These words have exact meanings in the rules below.

- **Contact:** the Well's signal is above its threshold. The DFM checks every millisecond.
- **Event:** one feeding bout. It starts when contact begins, and ends once the signal has stayed below the threshold for `EventGapMs` (default 100 ms), so a fly dipping in and out counts once. Contact that starts while the Well's own Activation is running doesn't start an Event, and that bout still isn't one if it carries on after the Activation ends: the next Event is the first contact after the signal has then stayed below the threshold for `EventGapMs`. Light from a linked Well doesn't matter here.
- **Activation:** one period during which the Paradigm lights the LED.
- **Requirement and Progress** (ratio types only): the number of Events needed for the next Activation, and how many have happened so far.

### Acclimation

`FixedInterval`, `ProgressiveRatio` and `FixedRatio` accept `Acclimation: N`. Each Well then starts with N closed-loop Activations: contact lights the LED, and it stays lit for `ActivationMs` after contact ends. Each time the LED comes on is one Activation, so a fly that comes back after the light has gone off counts again, even within the same Event. The Well switches to the main rule when its Nth Activation ends.

- This is counted for each Well separately, so every fly experiences exactly N Activations before the main rule starts.
- The data file shows each Well's Phase: `A` during Acclimation, `M` (Main) after.
- The old method (frequency above 512) gave N − 1. See [Converting old programs](#converting-old-programs).

### When a Well's progress carries over

Each Well remembers where it is in its Paradigm: Acclimation or Main, its Requirement and Progress, and any timers.

- If the next Interval uses the **same Paradigm**, all of that carries on. This includes a Repeating Program starting a new Cycle, and Intervals that only change thresholds or `Dark`.
- If the next Interval uses a **different Paradigm**, every Well starts that Paradigm fresh, including any Acclimation.
- The Activation counts in the data file run for the whole recording, whatever the Paradigm.

So to change thresholds in the middle of a progressive-ratio run without starting the ratio again, keep the same Paradigm name in both Intervals.

## The six Paradigm types

In the examples, the A wells (1A, 2A …) have a threshold of 20 and the B wells are `Off`.

### OpenLoop

The LED is lit for the whole Interval, whatever the fly does. A Well with the threshold `Off` stays dark. Any other threshold is ignored, so write `On`.

No other settings.

```
[Paradigm Open]
Type: OpenLoop

[DFM]
ID: 1
Interval: Open, Dark, On,On,On,On,On,On,On,On,On,On,On,On, 1440
```

An open-loop schedule of 3 minutes on and 12 minutes off, repeated:

```
[DFM]
ID: 1
ProgramType: Repeating
Interval: Open, Dark, On,On,On,On,On,On,On,On,On,On,On,On, 3
Interval: Open, Dark, Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off, 12
```

### ClosedLoop

The LED is lit during contact and for `HoldMs` after it ends.

| Setting | Meaning | Default |
|---|---|---|
| `HoldMs` | How long the LED stays on after contact ends. 500–1000 stops it flickering while the proboscis moves in and out of the food. | 0 |
| `MaxOnMs` | The longest one Activation can last, measured from when the LED came on. The LED then stays off until the Event ends, and the next Event can light it again. 0 means no limit. | 0 |
| `EventGapMs` | See [Events](#contact-events-and-activations). Here it decides when a cut-off Event has ended. | 100 |

```
[Paradigm Closed]
Type: ClosedLoop
HoldMs: 500
MaxOnMs: 2500

[DFM]
ID: 2
Interval: Closed, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 1440
```

With `Linkage: 1,1,2,2,…`, a fly feeding from the A well lights both LEDs in its chamber. Feeding from the B well lights nothing. A single burst of light lasts at most 2.5 seconds.

### FixedInterval

Contact starts an Activation that lasts exactly `ActivationMs`, however long the fly feeds. A new Activation can't start until `LockoutMs` after the previous one started. After that, contact starts the next one, even if the fly has been feeding throughout.

| Setting | Meaning | Default |
|---|---|---|
| `ActivationMs` | How long each Activation lasts | required |
| `LockoutMs` | The shortest time from the start of one Activation to the start of the next | required |
| `EventGapMs` | See [Events](#contact-events-and-activations). Used only during Acclimation. | 100 |
| `Acclimation` | See [Acclimation](#acclimation) | 0 |

```
[Paradigm Interval1Min]
Type: FixedInterval
ActivationMs: 1000
LockoutMs: 60000

[DFM]
ID: 5
Interval: Interval1Min, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 360
```

A fly that starts feeding gets 1 second of light. It can't get more until a minute after that light came on. Then its next contact, or its current one if it is still feeding, starts the next second of light.

To start with 10 minutes of plain closed loop, use a ClosedLoop Paradigm for the first Interval:

```
[Paradigm Training]
Type: ClosedLoop
HoldMs: 1000

[DFM]
ID: 6
Interval: Training, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 10
Interval: Interval1Min, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 350
```

To start with a fixed number of closed-loop Activations instead, add `Acclimation: 10` to the FixedInterval Paradigm.

### NonFeeding

The reverse of closed loop: the LED is off during contact, and comes on `OnDelayMs` after contact ends. At the start of the Interval it comes on at once.

| Setting | Meaning | Default |
|---|---|---|
| `OnDelayMs` | How long after contact ends the LED comes back on. 500–1000 stops it flickering. | 0 |
| `MaxOnMs` | The longest the LED stays on before the fly feeds again. 0 means no limit. | 0 |

```
[Paradigm NotFeeding]
Type: NonFeeding
OnDelayMs: 500

[DFM]
ID: 1
Interval: NotFeeding, Dark, 20,20,20,20,20,20,20,20,20,20,20,20, 360
```

Every LED starts on. When a fly feeds, its LED goes off at once. It comes back on half a second after the fly stops feeding, and stays on until the fly feeds again.

### ProgressiveRatio

The fly has to feed in more and more separate bouts (Events) to earn each Activation. Once it meets the Requirement, the LED comes on for exactly `ActivationMs`. Events during an Activation don't count.

| Setting | Meaning | Default |
|---|---|---|
| `ActivationMs` | How long each Activation lasts | required |
| `Series` | How the Requirement grows: `Arithmetic` or `Exponential` | `Arithmetic` |
| `FirstRequirement` | Arithmetic only: Events needed for the first Activation | 1 |
| `Step` | Arithmetic only: how much the Requirement grows after each Activation | required for Arithmetic |
| `Scale`, `Rate` | Exponential only: see below. Decimals are allowed. | 5 and 0.2 |
| `Cap` | The largest Requirement, at most 65535 | 65535 |
| `EventGapMs` | See [Events](#contact-events-and-activations) | 100 |
| `Acclimation` | See [Acclimation](#acclimation) | 0 |

The Requirement for the k-th Activation is:

- **Arithmetic:** FirstRequirement + Step × (k − 1). With `Step: 10` and `Cap: 200`, the Requirements are 1, 11, 21, 31 … 191, 200, 200 …
- **Exponential** (Richardson and Roberts, 1996): Scale × e^(Rate × k) − Scale, rounded. The defaults give 1, 2, 4, 6, 9, 12, 15, 20, 25, 32, 40, 50, 62, 77, 95 …

Acclimation Activations don't move the Requirement along: the first Main-phase Activation needs the first Requirement.

```
[Paradigm PR10]
Type: ProgressiveRatio
ActivationMs: 500
Step: 10
Cap: 200
Acclimation: 10

[DFM]
ID: 5
Interval: PR10, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 360
```

Each fly first gets 10 closed-loop Activations. Its next feeding bout earns half a second of light, then 11 more bouts earn the next, then 21 more, and so on, up to 200.

For a time-based start instead, run a ClosedLoop Paradigm for the first Interval and the ProgressiveRatio Paradigm after it, as in [A first Program](#a-first-program).

### FixedRatio

Every `Ratio`-th Event starts an Activation of exactly `ActivationMs`. The first comes at Event number `Ratio`.

| Setting | Meaning | Default |
|---|---|---|
| `ActivationMs` | How long each Activation lasts | required |
| `Ratio` | Events per Activation | required |
| `EventGapMs` | See [Events](#contact-events-and-activations) | 100 |
| `Acclimation` | See [Acclimation](#acclimation) | 0 |

```
[Paradigm FR5]
Type: FixedRatio
ActivationMs: 500
Ratio: 5

[DFM]
ID: 6
Interval: FR5, Dark, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 360
```

Every fifth feeding bout earns half a second of light.

## DFM sections and Intervals

```
[DFM]
ID: 3
ProgramType: Repeating
Linkage: 1,2,3,4,5,6,7,8,9,10,11,12
Interval: Closed, Dark, 20,20,20,20,20,20,20,20,20,20,20,20, 120
Interval: Closed, Lit, Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off,Off, 120
```

- **`ID`** comes first: the number set on the DFM's dials, 1–98. Each DFM has one section. (99 is the Environmental Monitor.)
- **`ID: All`** instead of a number makes the section apply to every connected DFM that has no section of its own, the Environmental Monitor excepted. At most one section can say this. The `OptoTest` programs in `FLICPrograms` use it, so they run on whatever DFMs are connected.
- **`ProgramType`** and **`Linkage`** override the `[General]` values for this DFM.
- **`Interval`** lines run in the order written.

A DFM that is connected but has no section, and no `ID: All` section to fall back on, is given every Well `Off` for the whole experiment.

### Interval lines

```
Interval: Paradigm, Dark or Lit, 12 thresholds, minutes
```

- **Paradigm:** the name of a `[Paradigm]` section.
- **`Dark` or `Lit`:** `Dark` turns off the four indicator LEDs on top of the DFM (heartbeat, communication and so on) so they don't disturb the flies. `Lit` leaves them on.
- **12 thresholds,** one per Well, in the order 1A, 1B, 2A, 2B … 6A, 6B. Each one is:
  - a signal level from 1 to 1023: contact means the signal is above it. With `Baseline: Yes`, the level is measured from the Well's resting signal. 20 is a common choice. It is low, so check the data for food leaking between wells.
  - `On`: the LED is lit for the whole Interval, whatever the Paradigm.
  - `Off`: the LED is never lit by this Well (linkage can still light it).
- **Minutes:** how long the Interval lasts. Decimals are allowed.

### Program types

| Type | Behaviour | Cycle (in the data file) |
|---|---|---|
| `Linear` | Runs the Intervals in order, then stays in the last one until recording ends. | Always 1 |
| `Repeating` | Goes back to the first Interval after the last. | 1 for the first pass, 2 for the second … |
| `Circadian` | Like Repeating, but follows the clock: the Intervals must add up to 1440 minutes, and the first starts at midnight. | 1 on the start day, 2 on the next day … |
| `Constant` | Runs only the first Interval, for the whole recording. | Always 1 |

If recording lasts longer than a Linear program's Intervals, the last Interval continues. If it is shorter, the remaining Intervals don't run.

### Linkage

Linkage lights LEDs together. Wells with the same number form a group, and every LED in a group is lit whenever any Well in it is lit. Each Well still follows its own Paradigm: in a linked FixedRatio chamber, for example, each Well counts its own Events.

The common use is a choice chamber, where one fly has two wells, A and B:

```
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Interval: Closed, Dark, Off,20,Off,20,Off,20,Off,20,Off,20,Off,20, 120
```

Here only feeding from the B (right) well triggers the light, and it lights both LEDs in the chamber. Linkage can also give control flies in other chambers exactly the same light as treatment flies: give their wells `Off` and link them to a treatment well.

## The Environmental Monitor

```
[ENVMON]
ProgramType: Linear
Interval: 0,1,0,1,1,0,0,0,0,0,0,0,0,120
Interval: 1,0,0,0,0,1,1,0,0,0,0,0,0,120
```

The Environmental Monitor's section is unchanged from the old format. It has no ID. Each Interval line has 14 numbers:

1. Dark: 0 = no, 1 = yes.
2. Relay 1, Relay 2, Output 1, Output 2, Output 3, Output 4: non-zero is on, 0 is off.
3. Six numbers that are ignored.
4. The length in minutes.

In this example, Relay 1 and Outputs 1 and 2 are on for the first 2 hours. Then both relays are off, Outputs 3 and 4 are on, and the indicator LEDs are dark.

## Which DFMs can run what

| Needs DFM firmware 4.0.0 or later | Runs on firmware 2.0.0 and later, and on V2 DFMs | Also runs on firmware 1.0.5 |
|---|---|---|
| ProgressiveRatio, FixedRatio, and any Paradigm with Acclimation | NonFeeding | OpenLoop, ClosedLoop and FixedInterval |

- When a Program is loaded, the MCU warns about any DFM that can't run it, naming the DFM and the feature. Run Program then refuses to start until the DFM is updated or the Program changed.
- Firmware 1.0.5 (the DFMs from 2021, which show `1.0.5` on their page) also can't take a time above 65535 ms (about 65 seconds), and would run NonFeeding as fixed interval without any warning, so the MCU refuses both for such a DFM.
- Older firmware runs its own version of the rules it supports, so details can differ. It doesn't use `EventGapMs`, for example. Use firmware 4.0.0 for new experiments.
- The DFM's firmware version is on its page in the MCU (Firmware).

## What the data file records

Each DFM's data file keeps all its earlier columns in the same places. W1–W12 are the Well signals. `OptoFreq`, `OptoPW` and `Dark` give the settings of the Interval that was running.

These columns follow them:

| Column | Meaning |
|---|---|
| `Interval` | Which Interval was running, counting from 1 in the order of the `[DFM]` section. 0 for the records before the first Interval, while the baseline is taken |
| `Cycle` | Which Cycle (see [Program types](#program-types)) |
| `Paradigm` | The Paradigm's name |
| `Phase1`–`Phase12` | `A` for Acclimation or `M` for Main, per Well |
| `Activations1`–`Activations12` | Activations per Well since recording started |
| `Requirement1`–`Requirement12` | Ratio types only: Events needed for the next Activation |
| `Progress1`–`Progress12` | Ratio types only: Events counted towards it so far |
| `OnMs1`–`OnMs12` | How many ms the Well's LED was active (pulsing) in that 200 ms record, whether its Paradigm, `On` or linkage lit it |

Each row covers 200 ms. A value that doesn't apply is written `NA`, which pandas and R read as missing: Requirement and Progress for other types, Cycle and Paradigm before the first Interval, Interval and Cycle for an instruction outside the Program (such as all LEDs off after it ends), and all these columns with firmware older than 4.0.0.

For the full description of every column, for writing analysis software, see [DataFileColumns.md](DataFileColumns.md).

On the MCU, the DFM page shows the Paradigm, its type and the Interval and Cycle. Tick "Well details" to see each Well's Phase, Activations, Requirement, Progress and on-time in place of the plot.

## Converting old programs

Programs in the old format still load. You don't have to change them unless they use progressive ratio or event-based acclimation.

### What happens to an old program

- **Old Interval lines** with 14 numbers (dark, 12 thresholds, minutes) or 19 numbers (with frequency, pulse width, decay, delay and max time on) still work. One file can mix old and new lines.
- **Dark:** 0 means `Lit`, and any other number means `Dark`.
- **Thresholds:** 0 means `On`, and -1 (or anything above 1023) means `Off`.
- **The Opto settings** (`OptoFrequency`, `OptoPW`, `OptoDecay`, `OptoDelay`, `MaxTimeOn`) in force for each Interval become a Paradigm, named after its settings, for example `ClosedLoop-40Hz-8ms-Hold500-MaxOn0`:

| Old settings | Becomes |
|---|---|
| `OptoDelay` 0 | ClosedLoop: `HoldMs` = OptoDecay, `MaxOnMs` = MaxTimeOn (-1 counts as 0, no limit). With thresholds of 0 this is the old open loop, because 0 now means `On`. |
| `OptoDelay` above 0 and `MaxTimeOn` 0 | FixedInterval: `ActivationMs` = OptoDecay, `LockoutMs` = OptoDelay |
| `OptoPW` above 32768 | NonFeeding: `PulseWidth` = OptoPW − 32768, `OnDelayMs` = OptoDelay, `MaxOnMs` = OptoDecay |
| `OptoDelay` and `MaxTimeOn` both above 0 (progressive ratio) | **Refused.** Rewrite it, see below. |
| `OptoFrequency` above 500 (acclimation bits) | **Refused.** Rewrite it, see below. |

Intervals with identical old settings become the same Paradigm, so a Well's progress carries over between them.

### Rewriting progressive ratio

The old progressive ratio counted milliseconds of contact. The DFM checks every millisecond, so a 1-second bout counted as 1000 "licks". The new ProgressiveRatio counts Events (feeding bouts), so the numbers mean something quite different and can't be converted automatically. Choose a new `Step` (or Series) in Events.

Old:

```
[DFM]
ID: 1
ProgramType: Repeating
Interval: 0,20,-1,20,-1,20,-1,20,-1,20,-1,20,-1,40,8,500,0,0,30
Interval: 0,20,-1,20,-1,20,-1,20,-1,20,-1,20,-1,40,8,500,1000,1000000000,330
```

New: 30 minutes of closed loop with a 500 ms hold, then progressive ratio with half-second Activations:

```
[Paradigm Closed]
Type: ClosedLoop
HoldMs: 500

[Paradigm PR]
Type: ProgressiveRatio
ActivationMs: 500
Step: 5

[DFM]
ID: 1
ProgramType: Repeating
Interval: Closed, Lit, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 30
Interval: PR, Lit, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 330
```

### Rewriting event-based acclimation

The old way packed the number of acclimation events into the high bits of `OptoFrequency`, so 10 events at 40 Hz was written 5160. Now it is a setting. The old method also gave one fewer than asked, so the new Program gives exactly 10.

Old:

```
Interval: 0,20,-1,20,-1,20,-1,20,-1,20,-1,20,-1,5160,8,500,1000,1000000000,360
```

New:

```
[Paradigm PR]
Type: ProgressiveRatio
Frequency: 40
PulseWidth: 8
ActivationMs: 500
Step: 5
Acclimation: 10

[DFM]
ID: 1
Interval: PR, Lit, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 360
```

### Other changes from the old document

- Errors are now reported with the line number, and a Program with an error doesn't load. Before, it just didn't appear.
- Unknown settings stop the load. The old loader ignored them, so check old files for lines such as `OptoLid`, which never did anything.
- `StartTime` also accepts `HH:MM`.
- `Constant` programs now run their first Interval. Before, they never sent it to the DFMs.
- The Well signals in the data file no longer have 65536 added while a fly is in training. With firmware 4.0.0, the Phase columns report Acclimation instead.
