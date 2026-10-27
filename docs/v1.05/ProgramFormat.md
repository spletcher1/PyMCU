# Stand-Alone MCU Programming Conventions

**For FLIC systems with version 1.05 DFM boards**

> **Coming soon: the version 4.0 FLIC system.** The version 4.0 FLIC system is due for release in the first quarter of 2027. It adds progressive-ratio and fixed-ratio reinforcement based on feeding bouts, optional acclimation, and per-Well records of light exposure and progress in the data file. For more information, contact Flidea at [info@flidea.tech](mailto:info@flidea.tech).

A program tells the Stand-Alone MCU when to record, for how long, and how the LEDs in each DFM's OptoLid respond to feeding. This guide describes program files for DFM boards with firmware version 1.05, which the MCU shows as `1.0.5` on each DFM's page.

## Contents

- [Getting a program onto the MCU](#getting-a-program-onto-the-mcu)
- [A complete example](#a-complete-example)
- [How a program file is laid out](#how-a-program-file-is-laid-out)
- [The [General] section](#the-general-section)
- [How the LEDs respond](#how-the-leds-respond)
- [The [DFM] section](#the-dfm-section)
- [The [ENVMON] section](#the-envmon-section)
- [When the MCU refuses a program](#when-the-mcu-refuses-a-program)
- [Changes from the 2022 edition](#changes-from-the-2022-edition)
- [Contact](#contact)

## Getting a program onto the MCU

1. Write the program as a plain text file with the extension `.txt`, for example in Notepad.
2. Save it in a folder named `FLICPrograms` at the top level of a USB stick. The folder name is case sensitive.
3. Insert the USB stick into the MCU and press **Programs → Custom → Get (USB)**. Every `.txt` file in the folder is copied to the MCU.
4. Choose the file on the **Programs → Custom** screen and press **Load**.

The MCU checks the whole file as it loads. If anything is wrong, nothing is loaded and the MCU names the line and the problem. See [When the MCU refuses a program](#when-the-mcu-refuses-a-program).

## A complete example

```
# An 18-hour experiment.
# DFM 1: open loop, 3 minutes of light and 12 minutes without, repeated.
# DFM 2: closed loop for 12 hours, then 6 hours without light.
[General]
ExpDurationMin: 1080
OptoFrequency: 40
OptoPW: 8
OptoDecay: 1000
Baseline: Yes

[DFM]
ID: 1
ProgramType: Repeating
Interval: 1,0,0,0,0,0,0,0,0,0,0,0,0,3
Interval: 1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,12

[DFM]
ID: 2
ProgramType: Linear
Interval: 1,20,20,20,20,20,20,20,20,20,20,20,20,720
Interval: 1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,360
```

- Recording starts at the beginning of the next minute after the program loads, because no `StartTime` is given, and lasts 1080 minutes (18 hours).
- When an LED is on, it pulses at 40 Hz with 8 ms pulses.
- **DFM 1** alternates between all LEDs on (threshold `0`) for 3 minutes and all LEDs off (threshold `-1`) for 12 minutes, until recording ends.
- **DFM 2** lights a Well's LED whenever that Well's signal rises more than 20 above its resting level, and keeps it on for 1 second (`OptoDecay: 1000`) after the signal falls back. After 12 hours, every LED stays off.
- The first number of each Interval line, `1`, turns off the indicator LEDs on top of the DFM so they don't disturb the flies.

## How a program file is laid out

A program is a plain text file divided into sections. Each line is one of:

| Line | Example |
| --- | --- |
| A section heading, in square brackets | `[General]` |
| A setting, written `Name: value` | `ExpDurationMin: 120` |
| A comment, starting with `#` | `# Choice chambers, B wells only` |
| Blank | |

- A program has up to three kinds of section:
  - **`[General]`** holds settings for the whole experiment and the defaults for every DFM.
  - **`[DFM]`** holds the program for one DFM. A program can have one for each DFM.
  - **`[ENVMON]`** holds the program for the Environmental Monitor, if you use its relays and outputs.
- Section and setting names can be written in any case: `[general]`, `EXPDURATIONMIN` and `expDurationMin` all work. Spaces around values don't matter.
- A comment must be on a line of its own.
- Numbers are whole numbers, except `ExpDurationMin` and the length of an Interval, which may have decimals.
- The MCU checks every line. An unknown section or setting, a setting in the wrong section, or a value it can't use stops the load, so a misspelling never goes unnoticed.

## The [General] section

`[General]` sets the experiment's timing and baseline, and the default light settings and program type for every DFM. A `[DFM]` section can override the defaults for its own DFM.

| Setting | Meaning | Default |
| --- | --- | --- |
| `StartTime` | When recording starts, on a 24-hour clock: `HH:MM` or `HH:MM:SS` for today, or `MM/DD/YYYY HH:MM:SS` for another day. The **Now** button on the program screen also sets it. | The start of the next minute after the program loads |
| `ExpDurationMin` | How long recording lasts, in minutes. Always set it. Together with `StartTime`, it sets when recording ends. | 1 |
| `ProgramType` | How each DFM steps through its Intervals: `Linear`, `Repeating`, `Circadian` or `Constant`. See [Program types](#program-types). | `Linear` |
| `OptoFrequency` | How many times per second an LED pulses while it is on, from 1 to 500 Hz. | 40 |
| `OptoPW` | How long each pulse lasts, in ms. It must be shorter than one period (1000 ÷ `OptoFrequency` ms). | 8 |
| `OptoDecay` | How long an LED stays on after the signal falls below the threshold, in ms. In fixed interval, how long each light period lasts. From 0 to 65,535. | 0 |
| `OptoDelay` | Above 0, selects fixed interval: the time from the start of one light period to the earliest start of the next, in ms. From 0 to 65,535. | 0 |
| `MaxTimeOn` | The longest an LED can stay on in one period in closed loop, in ms. 0 means no limit. From 0 to 65,535. | 0 |
| `Linkage` | 12 whole numbers, one per Well. Wells with the same number light together. See [Linkage](#linkage). | `1,2,3,4,5,6,7,8,9,10,11,12` (no linkage) |
| `Baseline` | `Yes` measures each Well's resting signal when recording starts, and thresholds are measured from it. `No` compares thresholds with the raw signal. | `Yes` |

- `StartTime`, `ExpDurationMin` and `Baseline` can only be set in `[General]`. They apply to every DFM.
- A setting that is left out takes its default. For example, this `[General]` section starts recording when the program loads, runs every DFM as a linear program with 40 Hz, 8 ms pulses, and no linkage:

  ```
  [General]
  ExpDurationMin: 120
  Baseline: Yes
  ```

- With `Baseline: Yes`, each Well's resting signal is the average of its first 10 readings after recording starts, which takes about 2 seconds. A DFM starts its first Interval only once that is done, so its LEDs stay off for those first seconds, even in open loop. The data file always records the raw signal.

This section starts recording at 1:13 AM and records for 2 hours, until 3:13 AM:

```
[General]
StartTime: 01:13:00
ExpDurationMin: 120
ProgramType: Linear
OptoFrequency: 30
OptoPW: 8
OptoDelay: 0
OptoDecay: 500
MaxTimeOn: 2500
Linkage: 1,2,2,4,5,6,7,8,9,10,11,12
Baseline: Yes
```

- LEDs pulse at 30 Hz with 8 ms pulses: each period is about 33 ms, so an LED is lit for about 24% of the time it is on.
- `OptoDelay` is 0, so this is closed loop: an LED comes on as soon as its Well's signal exceeds the threshold, and stays on for half a second (`OptoDecay: 500`) after it falls back.
- If a Well's signal stays above the threshold for more than 2.5 seconds, `MaxTimeOn` turns its LED off.
- Wells 2 and 3 (1B and 2A) share the linkage number 2, so both their LEDs light when either Well lights its LED.

## How the LEDs respond

Each Well's threshold and the `OptoDelay` and `MaxTimeOn` settings decide when its LED is on. While an LED is on, it pulses at `OptoFrequency` with pulses of `OptoPW` ms.

| Rule | How to set it | What the LED does |
| --- | --- | --- |
| **Always on** (open loop) | Threshold `0` | On for the whole Interval, whatever the fly does |
| **Always off** | Threshold `-1` | Never lit by this Well. Linkage can still light it. |
| **Closed loop** | A threshold from 1 to 1023, and `OptoDelay: 0` | On while the signal is above the threshold, and for `OptoDecay` ms after it falls below |
| **Fixed interval** | A threshold from 1 to 1023, `OptoDelay` above 0 and `MaxTimeOn: 0` | Contact starts a light period of exactly `OptoDecay` ms. A new one can't start until `OptoDelay` ms after the previous one started. |

### Closed loop

- `OptoDecay` of 500 to 1000 ms stops the LED flickering while the fly's proboscis moves in and out of the food.
- `MaxTimeOn` limits one on-period, including the `OptoDecay` time. When the limit is reached, the LED goes off even if the fly is still feeding. It can light again once the signal has stayed below the threshold for `OptoDecay` ms (at once if `OptoDecay` is 0).

### Fixed interval

- Contact lights the LED for exactly `OptoDecay` ms, however long the fly feeds.
- After `OptoDelay` ms from the start of that light period, the next contact starts another. If the fly is still feeding at that moment, the next light period starts at once.
- Set `OptoDecay` above 0: a version 1.05 DFM uses 1000 ms when it is 0.
- Make `OptoDelay` longer than `OptoDecay`. A light period can't last beyond `OptoDelay`.

For example, `OptoDecay: 1000` with `OptoDelay: 60000` gives a feeding fly 1 second of light, and at most one such second per minute.

### Not available on version 1.05 DFMs

These settings either ask for something a version 1.05 DFM can't do, or would be misread by it. The MCU refuses them rather than run something different from what the program asks.

| Feature | Setting that asks for it | What the MCU does |
| --- | --- | --- |
| Progressive ratio, or a delay before the LED can light again | `OptoDelay` and `MaxTimeOn` both above 0 | Refuses the program when it loads |
| Event-based acclimation (training) | `OptoFrequency` above 500 | Refuses the program when it loads |
| Non-feeding activation | `OptoPW` above 32768 | Loads the program, but won't run it on a version 1.05 DFM |
| Times above 65,535 ms (about 65 seconds) | `OptoDecay`, `OptoDelay` or `MaxTimeOn` | Loads the program, but won't run it on a version 1.05 DFM |

Progressive ratio, fixed ratio and event-based acclimation are part of the version 4.0 FLIC system. Contact Flidea at [info@flidea.tech](mailto:info@flidea.tech) for more information.

## The [DFM] section

A `[DFM]` section holds the program for one DFM. It starts with the DFM's `ID`, then any settings that override `[General]`, then its Interval lines.

```
[DFM]
ID: 1
ProgramType: Linear
Linkage: 1,2,3,4,5,6,7,8,9,10,11,12
Interval: 1,20,20,20,20,20,20,20,20,20,20,20,20,120
Interval: 0,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,120
Interval: 1,0,0,0,0,0,0,0,0,0,0,0,0,120
```

| Setting | Meaning |
| --- | --- |
| `ID` | Required, and first. The number set on the DFM's dials and shown on the MCU, from 1 to 98. Each DFM can have only one section. (99 is the Environmental Monitor.) |
| `ProgramType`, `Linkage` | Override the `[General]` values for this DFM. |
| `OptoFrequency`, `OptoPW`, `OptoDecay`, `OptoDelay`, `MaxTimeOn` | Override the `[General]` values for this DFM. Put them before the Interval lines: each Interval uses the values set above it. |
| `Interval` | One step of the program. Intervals run in the order written. |

In the example above, using the `[General]` section from the previous example:

- **First 2 hours:** the DFM runs dark, and each Well's LED lights when its signal exceeds 20. LEDs pulse at 30 Hz with 8 ms pulses and stay on half a second after feeding ends.
- **Hours 2 to 4:** the indicator LEDs on top of the DFM are on, and every OptoLid LED is off, whatever the flies do.
- **From hour 4 to the end of recording:** the DFM runs dark again, and every OptoLid LED is on.

`ID: All` in place of a number makes the section apply to every connected DFM that has no section of its own. The Environmental Monitor is excepted. Only one section can use it.

### Interval lines

```
Interval: dark, 1A, 1B, 2A, 2B, 3A, 3B, 4A, 4B, 5A, 5B, 6A, 6B, minutes
```

An Interval line has 14 numbers, separated by commas:

1. **Dark running:** `1` turns off the four indicator LEDs on top of the DFM (heartbeat, communication and so on), so they don't disturb the flies. `0` leaves them on.
2. **Twelve thresholds,** one per Well, in the order 1A, 1B, 2A, 2B … 6A, 6B. Each one is:
   - `0`: the LED is always on.
   - `-1`: the LED is never lit by this Well. Any value above 1023 also means this.
   - A signal level from 1 to 1023: contact means the signal is above it. With `Baseline: Yes`, the level is measured from the Well's resting signal. 20 is a common choice.
3. **Length** in minutes. It must be more than 0, and may have decimals.

To give one Interval its own light settings, add five numbers between the thresholds and the length: `OptoFrequency`, `OptoPW`, `OptoDecay`, `OptoDelay` and `MaxTimeOn`, for 19 numbers in all. For example, 10 Hz pulses with a 1 second decay for 30 minutes:

```
Interval: 1,20,20,20,20,20,20,20,20,20,20,20,20,10,8,1000,0,0,30
```

### Program types

| Type | Behavior |
| --- | --- |
| `Linear` | Runs the Intervals in order, then stays in the last one until recording ends. |
| `Repeating` | Goes back to the first Interval after the last, until recording ends. |
| `Circadian` | Repeats on the clock: the Intervals must add up to exactly 1440 minutes (24 hours), and the first starts at midnight. |
| `Constant` | Runs only the first Interval, for the whole recording. |

Recording time always takes precedence. If `ExpDurationMin` is shorter than a DFM's Intervals, recording ends partway through them. If it is longer, a Linear program stays in its last Interval until the end.

### Linkage

Linkage lights LEDs together. Wells with the same number form a group, and every LED in a group is on whenever any Well in it lights its LED.

Its most common use is a choice chamber, in which one fly has two wells, A on the left and B on the right. This section lights both LEDs in a chamber only when the fly feeds from the B well. It also sets 10 Hz pulses for this DFM alone:

```
[DFM]
ID: 1
ProgramType: Linear
OptoFrequency: 10
Linkage: 1,1,3,3,5,5,7,7,9,9,11,11
Interval: 0,-1,20,-1,20,-1,20,-1,20,-1,20,-1,20,120
```

Linkage can also give control flies exactly the same light as treatment flies: set the control Wells' thresholds to `-1` and give them the linkage number of a treatment Well.

### DFMs that aren't in the program

A DFM that is connected but has no `[DFM]` section, and no `ID: All` section to fall back on, keeps every LED off for the whole experiment. The MCU notes this on the Messages page, for example `DFM 3 not listed in program file. Adding simple program`. The DFM still records.

## The [ENVMON] section

The `[ENVMON]` section controls the Environmental Monitor's two relays and four output pins, which can switch external devices. It needs no `ID`, because the Environmental Monitor is always 99. It takes only `ProgramType` and `Interval` lines.

```
[ENVMON]
ProgramType: Linear
Interval: 0,1,0,1,1,0,0,0,0,0,0,0,0,120
Interval: 1,0,0,0,0,1,1,0,0,0,0,0,0,120
```

Each Interval line has 14 numbers:

1. **Dark running:** `1` turns off the indicator LEDs, `0` leaves them on.
2. **Relay 1, Relay 2, Output 1, Output 2, Output 3, Output 4:** `1` is on, `0` is off.
3. **Six numbers that are ignored.** Write them as `0`.
4. **Length** in minutes.

In this example, for the first 2 hours, Relay 1 and Outputs 1 and 2 are on. After that, both relays and Outputs 1 and 2 are off, Outputs 3 and 4 are on, and the indicator LEDs are dark until recording ends.

## When the MCU refuses a program

### When it loads

If anything in the file is wrong, nothing is loaded. A **Program not loaded** box names the file, the line and the problem, and the same message is added to the Messages page. Correct the file, copy it to the MCU again, and reload it.

| Message | Cause |
| --- | --- |
| `Line 1: Expected a section such as [General] before this line` | A setting before the first section heading |
| `Line 4: Expected 'Setting: value'` | A line with no colon |
| `Line 9: Unknown section [Setup]. Sections: [General], …` | A misspelled section heading |
| `Line 6: Unknown [General] setting 'OptoDuration'` | A misspelled setting |
| `Line 14: Unknown [DFM] setting 'Baseline'` | `StartTime`, `ExpDurationMin` or `Baseline` outside `[General]` |
| `Line 3: StartTime must be HH:MM, HH:MM:SS or MM/DD/YYYY HH:MM:SS, not '25:00'` | A start time that isn't a valid time |
| `Line 4: ProgramType must be Linear, Repeating, Circadian or Constant, not 'Loop'` | An unknown program type |
| `Line 9: Linkage must have 12 values, not 11` | Too few or too many linkage numbers |
| `Line 10: Baseline must be Yes or No` | Any other value |
| `Line 7: OptoDecay must be a whole number, not '1.5'` | A decimal or a word where a whole number is needed |
| `Line 5: OptoFrequency must be from 1 to 500` | A frequency of 0 |
| `Line 8: OptoDecay and OptoDelay can't be negative` | A negative time |
| `Line 8: Old progressive ratio settings (OptoDelay and MaxTimeOn both above 0) …` | Progressive ratio, which version 1.05 DFMs can't run |
| `Line 5: OptoFrequency above 500 is the old way of setting event-based acclimation. …` | Acclimation, which version 1.05 DFMs can't run |
| `Line 12: A [DFM] section must start with its ID` | A setting before the `ID` line |
| `Line 13: DFM IDs are 1 to 98` | An ID out of range |
| `Line 20: DFM 3 has two [DFM] sections` | The same ID twice |
| `Line 15: An Interval line without a Paradigm name has 14 or 19 numbers, not 13` | A missing or extra number |
| `Line 15: The first Interval value (dark running) must be 0 or 1` | Any other dark-running value |
| `Line 15: Thresholds are 0 (always on), -1 (always off) or a signal level, not -5` | A threshold below -1 |
| `Line 15: An Interval must last more than 0 minutes` | A length of 0 |
| `DFM 1: Circadian Intervals must add up to 1440 minutes, not 1200` | A Circadian program that isn't exactly 24 hours |

### When it runs on a version 1.05 DFM

Once a program has loaded, the MCU checks it against the firmware of every connected DFM. If a DFM can't run it, a **Compatibility Check** box says "This program can't run on every DFM, so it won't start." and names the DFM and the reason:

```
DFM 7 (firmware 1.0.5) can't run: times above 65535 ms need firmware 2.0.0
DFM 7 (firmware 1.0.5) can't run: the NonFeeding Paradigm type needs firmware 2.0.0
```

The first line is caused by an `OptoDecay`, `OptoDelay` or `MaxTimeOn` above 65,535. The second is caused by an `OptoPW` above 32768 (non-feeding activation).

Pressing **Run Program** repeats the check, in case a DFM has been changed since, and the program won't start until every DFM can run it. Change the program, or disconnect the DFM.

If a DFM turns out to have version 1.05 firmware only after the program has started, the MCU doesn't send it the Interval it can't run. The DFM keeps its previous instructions, and the Messages page shows, for example:

```
DFM 7 (firmware 1.0.5) can't run this Interval: times above 65535 ms need firmware 2.0.0
```

Each DFM's firmware version is shown on its page in the MCU.

## Changes from the 2022 edition

- Problems in a program file are reported, with the line number. Before, a program with a problem simply didn't appear on the program screen.
- Unknown settings, settings in the wrong section and values out of range stop the load. Before, some were silently ignored.
- The dark-running value in an Interval line must be `0` or `1`.
- `OptoDelay` and `MaxTimeOn` both above 0 is refused. The 2022 edition described this as a delay before the LED could light again.
- Times are limited to 65,535 ms, the most a version 1.05 DFM can hold.
- `StartTime` also accepts `HH:MM` and a date (`MM/DD/YYYY HH:MM:SS`).
- `ExpDurationMin` and Interval lengths may have decimals.
- An Interval line may give its own light settings (19 numbers).
- A `[DFM]` section with `ID: All` applies to every connected DFM without a section of its own.

## Contact

- **Questions and suggestions about programming:** Scott Pletcher, [spletch@umich.edu](mailto:spletch@umich.edu)
- **The version 4.0 FLIC system,** due for release in the first quarter of 2027: Flidea, [info@flidea.tech](mailto:info@flidea.tech)
