# FLIC User Guide: PyMCU 1.0.7 to 3.5.2

For MCUs running PyMCU 1.0.7, 2.0.0, 3.5.0, 3.5.1 or 3.5.2. Last updated: 2026-10-25.

This guide takes you through a FLIC experiment on an MCU with PyMCU older than 4.0: setting up the DFMs, writing and loading a Program, running it, and getting the data off. For each step it says what to do, what the MCU and the DFMs do in response, and where the versions differ.

For PyMCU 4.0, use [../UserGuide.md](../UserGuide.md) instead. Its screens, Program files and data files differ from the ones described here, and so do the other documents in the `docs` folder, which all describe 4.0. Everything a pre-4.0 MCU needs is therefore in this guide, including the Program file format ([section 13](#13-program-file-reference)) and the data file columns ([section 12](#12-step-7-get-the-data-off-the-mcu)).

Questions and suggestions: Scott Pletcher (spletch@umich.edu).

## Contents

1. [Which version do you have?](#1-which-version-do-you-have)
2. [The FLIC system](#2-the-flic-system)
3. [Words used in this guide](#3-words-used-in-this-guide)
4. [Before you start](#4-before-you-start)
5. [A tour of the MCU screen](#5-a-tour-of-the-mcu-screen)
6. [Step 1: Find the DFMs](#6-step-1-find-the-dfms)
7. [Step 2: Check each DFM on the Live Data page](#7-step-2-check-each-dfm-on-the-live-data-page)
8. [Step 3: Choose or write a Program](#8-step-3-choose-or-write-a-program)
9. [Step 4: Put the Program on the MCU and load it](#9-step-4-put-the-program-on-the-mcu-and-load-it)
10. [Step 5: Set the start time and run](#10-step-5-set-the-start-time-and-run)
11. [Step 6: Watch the experiment](#11-step-6-watch-the-experiment)
12. [Step 7: Get the data off the MCU](#12-step-7-get-the-data-off-the-mcu)
13. [Program file reference](#13-program-file-reference)
14. [Settings and maintenance](#14-settings-and-maintenance)
15. [Troubleshooting and known problems](#15-troubleshooting-and-known-problems)
16. [Appendix: the versions side by side](#16-appendix-the-versions-side-by-side)

## 1. Which version do you have?

Press **About** on the toolbar. The second line of the box gives the version, for example `Version: 3.5.2`.

| Version | Released | Runs on | Instructs DFM firmware | In brief |
|---|---|---|---|---|
| 1.0.7 | May 2024 | The original MCU, a Raspberry Pi 4 or earlier | 1.0.5 only | The 2022 software with one fix |
| 2.0.0 | May 2024, updated until October 2025 | Raspberry Pi 5 | 1.0.5 and 2.0.0 | Adds the firmware 2.0.0 light rules, light settings per Interval, and each DFM's firmware on its page |
| 3.5.0 | 9 October 2026 | Raspberry Pi 5 | 1.0.5 to 3.5.x | Reliable USB copying, a touch calendar for the start time, checked updates, a screen-off setting |
| 3.5.1 | 14 October 2026 | Raspberry Pi 4 or 5 | 1.0.5 to 3.5.x | Names the line of any mistake in a Program file, and refuses settings a DFM's firmware would misread |
| 3.5.2 | 16 October 2026 | Raspberry Pi 4 or 5 | 1.0.5 to 3.5.x | Starts on the whole minute, takes the baseline at the start of the recording, adds `ID: All` |

"3.5.x" in this guide means all three 3.5 versions. [Section 16](#16-appendix-the-versions-side-by-side) lists every difference in one table.

**PyMCU 2.0.0 was updated several times without a change of number.** This guide describes its last build. Builds from before December 2024 have no dark theme, and builds from before September 2024 can write a record twice when a DFM sends it again.

**Moving to a newer version.** On a 3.5.x MCU, 3.5.1 and 3.5.2 install with **Update MCU** ([section 14](#14-settings-and-maintenance)). An MCU on 1.0.7 or 2.0.0 can't install 3.5.x that way: it has to be set up again with a new operating system. That is a job for lab staff, following `docs/MCUSetup.md` from the release being installed (tag `v3.5.2` in the PyMCU repository).

## 2. The FLIC system

FLIC (the Fly Liquid-food Interaction Counter) measures feeding. Each Well holds a drop of liquid food. When a fly touches the food, the Well's electrical signal rises, so a recording of the signal shows when, how often and for how long each fly fed. With an OptoLid on top, every Well also has its own LED, which can be switched on in response to what the fly does, to deliver optogenetic light as a reward or a punishment for feeding.

### The parts

| Part | What it is | What it does |
|---|---|---|
| **DFM** | A feeding monitor board with twelve Wells, in six chambers of two | Measures every Well's signal, switches each Well's LED by the settings it was last sent, and stores a Status record every 200 ms until the MCU collects it |
| **OptoLid** | The lid with one LED above each Well | Delivers the light the DFM switches on |
| **Environmental Monitor** | A board with ID 99 | Measures temperature, humidity and light, and can switch two relays and four outputs on a schedule |
| **MCU** | A Raspberry Pi with a touch screen, running PyMCU | Runs the Program's schedule, sends each DFM its settings when an Interval starts, collects the records and writes the data files |
| **Bus** | One RS-485 cable shared by all the DFMs and the Environmental Monitor | Carries the MCU's requests and the boards' replies. The MCU talks to one board at a time, by its ID |
| **USB stick** | Any stick, with the right folders on it | Carries Programs to the MCU, data from it and software updates to it |

### Who decides what

- **The DFM decides the light.** It compares each Well's signal with that Well's threshold and switches the LED by the settings of the Interval it was last sent. The MCU never switches an LED itself, so if the MCU is slow or the bus is briefly disconnected, the light keeps following the fly.
- **The MCU decides the schedule.** It sends each DFM new settings when an Interval starts. A DFM changes Interval only when the MCU tells it to.
- **The DFM keeps its records until the MCU confirms it has them.** The MCU collects them every few seconds and acknowledges each reply; records that weren't acknowledged are sent again.
- **Your analysis decides what counts as feeding,** from the recorded signals. The thresholds in the Program control only the light.

### The workflow

1. Set the DFMs' IDs, connect them and power everything on ([section 4](#4-before-you-start)).
2. **Find DFM** on the MCU ([section 6](#6-step-1-find-the-dfms)).
3. Check each DFM's signals and LEDs ([section 7](#7-step-2-check-each-dfm-on-the-live-data-page)).
4. Choose a simple recording or write a Program ([section 8](#8-step-3-choose-or-write-a-program)).
5. Copy the Program to the MCU and **Load** it ([section 9](#9-step-4-put-the-program-on-the-mcu-and-load-it)).
6. Set the start time and press **Run Program** ([section 10](#10-step-5-set-the-start-time-and-run)).
7. Watch the experiment ([section 11](#11-step-6-watch-the-experiment)).
8. **Export Data** to a USB stick ([section 12](#12-step-7-get-the-data-off-the-mcu)).

## 3. Words used in this guide

| Word | Meaning |
|---|---|
| **Well** | One feeding site. The twelve Wells are named 1A, 1B, 2A, 2B … 6A, 6B and numbered 1 to 12 in that order, so Well 1 is 1A and Well 2 is 1B. |
| **Chamber** | One row of a DFM: Wells nA and nB. In a choice (two-well) experiment one fly has both Wells; in a single-well experiment each Well has its own fly. |
| **Signal** | A Well's reading, 0 to 1023. It rises when a fly touches the food. |
| **Baseline** | A Well's resting signal, the average of its first 10 readings. With `Baseline: Yes`, thresholds are measured from it. |
| **Threshold** | The signal level at which a Well counts as in contact with the food. `0` means the LED is always on and `-1` that the Well never lights it. |
| **Activation** | One period during which a Well's LED is lit. |
| **Interval** | One timed step of a DFM's Program, with its dark-running setting, its twelve thresholds and its length. |
| **Program** | A text file that says how long to record and what each DFM's LEDs do, Interval by Interval. |
| **Opto settings** | `OptoFrequency`, `OptoPW`, `OptoDecay`, `OptoDelay` and `MaxTimeOn`: how the LEDs pulse and which rule decides when they are on ([section 13.5](#135-how-the-leds-respond)). |
| **Linkage** | Wells grouped so that their LEDs light together. |
| **Dark running** | The DFM's own indicator LEDs switched off for an Interval, so they don't disturb the flies. It doesn't affect the OptoLid. |
| **Status record** | What a DFM reports for every 200 ms: the twelve signals, the LED state and its error flags. One record is one row of the data file. |

## 4. Before you start

### 4.1 DFMs

**IDs.** Every board on the bus needs its own ID, set on the DFM's two rotary dials: tens and ones, so dials at 1 and 2 give ID 12.

- DFMs use IDs 1 to 98. ID 99 is the Environmental Monitor, and ID 0 is never found.
- The dials are read only when the board powers up. After changing them, switch the DFM off and on again.

**Firmware.** Which DFMs an MCU can run depends on its PyMCU version and each board's firmware:

| DFM firmware | 1.0.7 | 2.0.0 | 3.5.0 | 3.5.1, 3.5.2 |
|---|---|---|---|---|
| 1.0.5 (2021 boards) | Yes | Yes | Yes | Yes, and refuses settings the board would misread |
| 2.0.0 | Records only | Yes | Yes | Yes |
| 2.0.1 | Records only | Records only | Yes | Yes |
| 3.5.0, 3.5.1 | Records only | Records only | Yes | Yes |
| 4.0.0 | No | No | No | No, and says so |

"Records only" means the board is found and recorded, but it refuses the MCU's instructions, which are in the older format, so its LEDs never follow the Program. The DFM page then usually shows **P Size** ticked ([section 7](#7-step-2-check-each-dfm-on-the-live-data-page)). A 4.0.0 board needs PyMCU 4.0. Boards of different firmware can share a bus.

From 2.0.0 the DFM page shows each board's firmware. Boards with firmware 1.0.5 can't answer the MCU's question, so they are shown as `1.0.5`. PyMCU 1.0.7 doesn't ask and doesn't show it.

Installing DFM firmware is a job for lab staff.

**Indicator LEDs.** The DFM's four indicator LEDs show its heartbeat, its communication and other states. An Interval with dark running (`1` as the first number of its line) turns them off.

### 4.2 The MCU

A new MCU is set up once, by lab staff. After that it starts PyMCU full screen whenever it is powered on.

- **Clock.** Every time in the data comes from the MCU's clock. Check it on the status bar, and set it in Settings ([section 14](#14-settings-and-maintenance)) if it is wrong. A clock battery keeps the time while the MCU is off.
- **Storage.** Keep at least 1 GB free: export old recordings and delete them from the MCU ([section 12](#12-step-7-get-the-data-off-the-mcu)). PyMCU 3.5.x warns at start-up when less is free. **PyMCU 1.0.7 and 2.0.0 don't start at all** when less than 1 GB is free ([section 15](#15-troubleshooting-and-known-problems)).

### 4.3 A USB stick

The MCU uses folders with these exact names, case included, at the top level of the stick:

| Folder | Used for | 1.0.7 and 2.0.0 | 3.5.x |
|---|---|---|---|
| `FLICPrograms` | Program files to copy to the MCU | Read from the first stick found | Read from the first stick that has the folder |
| `FLICData` | Receives the recordings when you export them | Created on the first stick found if it isn't there | Must already be on the stick; create it empty before the first export |
| `FLICUpdates` | A PyMCU update | Exactly one `.tgz` file in this folder | One `.mcu` file, in this folder or at the top level |

With 1.0.7 and 2.0.0, plug in only one stick at a time: the MCU uses the first one it finds, whatever is on it. With 3.5.x, a stick without the needed folder is ignored for that action.

## 5. A tour of the MCU screen

The screen has a toolbar along the top, a page in the middle and a status bar along the bottom. The status bar shows the date and time on the right, and on the left a short message for a few seconds after each action, for example "3 DFMs found." or "USB connected...". The toolbar is the same in every version.

| Button | What it does |
|---|---|
| **Live Data** | Shows the DFM page: the live signals and status of one DFM ([section 7](#7-step-2-check-each-dfm-on-the-live-data-page)). |
| **Programs** | Shows the Program page: the loaded Program, the start time and the run button ([sections 8 to 10](#8-step-3-choose-or-write-a-program)). |
| **Messages** | Shows the Messages page: what the MCU and the DFMs have reported ([section 11](#11-step-6-watch-the-experiment)). |
| **Clear Msg** | Clears the messages, after asking. |
| **Find DFM** | Searches the bus for DFMs and the Environmental Monitor ([section 6](#6-step-1-find-the-dfms)). |
| **Clear DFM** | Disconnects from all the boards without asking: stops reading them, forgets them and the loaded Program, and clears the messages. Use it before **Find DFM** when you have added, removed or renumbered a board. |
| **Export Data** | Copies every recording on the MCU to a USB stick ([section 12](#12-step-7-get-the-data-off-the-mcu)). |
| **Delete Data** | Deletes every recording on the MCU, after asking twice. |
| **Outputs** | Switches every LED of every DFM on, or off again, to test the OptoLids ([section 7](#testing-the-leds-with-outputs)). |
| **Power Off** | Shuts the MCU down, after asking twice. Wait for the screen to go dark before unplugging it. |
| **About** | Shows the PyMCU version, network address and free storage, and opens Settings ([section 14](#14-settings-and-maintenance)). |

While a Program is running, everything that could disturb it is locked: Clear Msg, Clear DFM, Export Data, Delete Data, Outputs, Power Off, the Program buttons, the start time, and Settings. **Stop Program** and the pages stay available.

## 6. Step 1: Find the DFMs

**Do:** power on the DFMs and the Environmental Monitor, wait a few seconds for them to start, then press **Find DFM**.

**What happens:**

1. The MCU clears the messages and asks every ID from 1 to 99 in turn whether a board is there. The status bar says "Searching for DFMs." and the search takes a few seconds.
2. Each board that answers gets a button on the left of the Live Data page, `DFM 1`, `DFM 2` and so on, or `EnvMon` for the Environmental Monitor, and a message such as "DFM 1 found" or "Environmental monitor found".
3. From 2.0.0, the MCU asks each DFM for its firmware version, which decides how it talks to that board. A 1.0.5 board can't answer and is shown as `1.0.5`. In 2.0.0 and 3.5.0 the question ticks that board's **P Type** box once; that is harmless, and from 3.5.1 the MCU clears it. From 3.5.1, a board with firmware 4.0.0 gets the message "DFM 7 runs firmware 4.0.0, which needs PyMCU 4.0.0 or later" and is then left alone.
4. A simple 3-hour recording with every LED off is loaded, starting at the next minute, so a recording can be started straight away.
5. The Live Data page opens on the first board. From now until a recording starts, the MCU reads only the board on screen, about three times a second, so its display stays live.

The status bar ends with "N DFMs found." If it says "No DFMs found.", check the power, the bus cable and the IDs, then press **Find DFM** again.

**Find DFM** stays greyed out once boards are found. To change the set of boards, press **Clear DFM**, then **Find DFM**.

> **PyMCU 2.0.0 and the Environmental Monitor.** 2.0.0 can't show the Environmental Monitor's page, and with a monitor on the bus, Find DFM can close PyMCU. Unplug the monitor from the bus, or use 1.0.7 or 3.5.x.

## 7. Step 2: Check each DFM on the Live Data page

Before an experiment, look at every DFM: its signals should be steady at rest, its LEDs should light, and (from 2.0.0) its firmware should be one this PyMCU instructs ([section 4.1](#41-dfms)).

**Do:** tap a DFM's button on the left. Its label turns bold and the page shows that board. The MCU starts reading it instead of the previous one.

The button's colour shows the board's state:

| Colour | Status | Meaning |
|---|---|---|
| Black (white in the dark theme) | Read | Being read, no recording |
| Green | Record (`Rec` in 3.5.2) | Recording |
| Red | Error | A reply was damaged, or records were missing from it |
| Blue | Miss | The board didn't answer |

### The plot

The plot has one column per chamber, Row 1 to Row 6. The blue dot is the chamber's A Well and the red dot its B Well, and the height is the Well's signal minus its baseline (the plain signal until a baseline has been measured).

- At rest a Well sits low and steady. When a fly feeds, or you touch the food, its dot jumps up, and falls back when contact ends.
- The scale runs from 0 to 1000. Tick **Zoom Plot** to show 0 to 100, for checking small resting levels.

### The panels on the right

**Environment** shows the Environmental Monitor's Temperature, Humidity and LUX (greyed out when there is no monitor) and the DFM's own Input Voltage.

**Status:**

| Row | Shows |
|---|---|
| Dark Mode | `Yes` while the DFM's indicator LEDs are switched off by dark running |
| Frequency | The LED pulse frequency the DFM is using, in Hz |
| Pulse Width | The LED pulse width the DFM is using, in ms |
| Optostate | Which LEDs are lit at that instant, as a hexadecimal number: `0x000` none, `0x001` Well 1 only, `0xFFF` all twelve |
| Status | Read, Record (`Rec` in 3.5.2), Error, Miss, or None |
| Past Status | `Error` if the board has been in Error or Miss since it was found or the recording started, otherwise `Clear` |
| Firmware | The DFM's firmware version (from 2.0.0) |

**DFM Indicators** are the DFM's error flags. A box is ticked once its flag has been raised since the DFM was found or the recording started, so a tick tells you something happened even if it has stopped.

In 3.5.x the boxes are labelled by what they mean on that board's firmware, and each box's tooltip explains it:

| Box | Meaning | What to do |
|---|---|---|
| No Ack | The DFM didn't receive the MCU's acknowledgement for a reply, so it sent those records again. Nothing is lost. | Nothing, unless it is ticked constantly |
| Overflow | Firmware 3.5.0 and later only: the DFM's record store filled up before the MCU collected it, and the oldest records were overwritten. Records were lost. | Check the bus cable |
| P Type | A request had an unknown command | Report it if it recurs |
| DMA Tx, DMA Rx | Errors sending or receiving on the bus. The DFM recovers by itself. | Check the cable if it recurs |
| P Size | A request had the wrong length: noise on the bus, or an instruction in a format the board's firmware doesn't use | Check the cable; check the firmware table in [section 4.1](#41-dfms) |
| AI Int | Signal readings arrived before the last ones were used | Report it |
| O Int | The DFM's 1 ms clock ticked before it had finished the last millisecond | Report it |

Firmware older than 3.5.0 has no Overflow flag, so its page shows seven boxes.

In 1.0.7 and 2.0.0 the boxes always carry the same eight labels, whatever the firmware: **I2C**, **ID Ack**, **P Type**, **DMA Tx**, **DMA Rx**, **P Size**, **AI Int** and **O Int**. A missed acknowledgement ticks **ID Ack** on 1.0.5 boards and some 2.0.0 boards, and **I2C** on other 2.0.0 boards and on 2.0.1 boards. The version number doesn't tell which, so treat either box as No Ack. The other six mean what the table above says.

### Testing the LEDs with Outputs

**Do:** with no Program running, press **Outputs**. Press it again to switch off.

**What it does:** sets all twelve Wells of every DFM to always on, so every LED of each OptoLid lights at once. Use it to check that each OptoLid is connected and every LED works. A DFM gets the setting the next time the MCU talks to it: at once for the DFM on screen, and when you tap each of the others. The LEDs stay on until you press **Outputs** again or a Program's first Interval starts.

## 8. Step 3: Choose or write a Program

A Program says how long to record and what each DFM's LEDs should do, and when.

### Simple recordings without light

The Program page has buttons for **30 min**, **60 min**, **3 hours**, **6 hours**, **12 hours**, **24 hours** and **5 days**.

**What they do:** load a built-in Program that records every DFM for that long, starting at the next minute, with every LED off. Use them for plain feeding experiments. The Program page then shows it as `***ALL DFM***`. They work only after **Find DFM**; before that the status bar says "Load programs only after DFMs have been defined."

### Custom Programs

For light, write a Program file: a plain text file (`.txt`), for example in Notepad. This one works in every version. It is for choice chambers, and feeding from the A Well lights both LEDs of its chamber:

```
# Six hours of closed loop for choice chambers.
# Feeding from an A well lights both LEDs in its chamber.
[General]
ExpDurationMin: 360
OptoFrequency: 40
OptoPW: 8
OptoDecay: 500
Linkage: 1,1,3,3,5,5,7,7,9,9,11,11
Baseline: Yes

[DFM]
ID: 1
ProgramType: Linear
Interval: 1,20,-1,20,-1,20,-1,20,-1,20,-1,20,-1,360
```

- `[General]` sets the length (360 minutes), how the LEDs pulse (40 times a second, 8 ms each), how long they stay on after contact ends (500 ms), the Linkage (Wells 1 and 2 light together, 3 and 4, and so on) and baselining.
- `[DFM]` says what DFM 1 does: for 360 minutes, run dark (the first `1`), light a Well's LED when its signal is 20 above its resting level for each A Well, and never for the B Wells (`-1`). The last number is the length in minutes.

The rules a Program can ask for:

| Rule | What the light does | DFM firmware | PyMCU |
|---|---|---|---|
| Always on (open loop) | On for the whole Interval, whatever the fly does | Any | Any |
| Closed loop | On during contact and for `OptoDecay` ms after it, optionally cut off after `MaxTimeOn` | Any | Any |
| Fixed interval | Contact gives exactly `OptoDecay` ms of light, then none until `OptoDelay` ms after it started | Any | Any |
| Non-feeding activation | Off during contact; on after a set time without contact | 2.0.0 and later | 2.0.0 and later |
| Progressive ratio | Each Activation needs more accumulated contact than the last | 2.0.0 and later | 2.0.0 and later |
| Training, then progressive ratio | A set number of simple Activations first, then progressive ratio | 2.0.0 and later | 2.0.0 and later |

A DFM can step through several Intervals, each with its own thresholds (and from 2.0.0 its own opto settings), and run them once (`Linear`), over and over (`Repeating`) or on a 24-hour clock (`Circadian`). Everything about writing Programs is in [section 13](#13-program-file-reference).

**Ready-made Programs** are in the `FLICPrograms` folder of the PyMCU repository, at the tag of your release. Updates don't install them; copy them to the MCU with **Get (USB)**.

| Program | Use | Versions |
|---|---|---|
| `OptoLidOutputTest` | On DFM 1: lights each LED alone in Well order, then all off, then all on, repeating, to check an OptoLid | All |
| `OptoTest1_OpenLoop` … `OptoTest6_TrainingFirst` | Ten minutes of one rule on every connected DFM, with thresholds 50 above baseline. Touch a Well to see the rule work; the comment at the top of each file says what to expect. Tests 4 to 6 need DFM firmware 2.0.0 or later. | 3.5.2 only, because they use `ID: All` |

## 9. Step 4: Put the Program on the MCU and load it

**Do:**

1. Copy the Program file into the `FLICPrograms` folder of a USB stick. With 1.0.7 and 2.0.0 the extension must be lower case, `.txt`.
2. Plug the stick into the MCU. The status bar shows "USB connected...".
3. Press **Programs**, then **Custom**. This opens the Program files page: the files on the MCU on the right, a preview on the left.
4. Press **Get (USB)**.
5. Tap the file in the list and check the preview.
6. Press **Load**.

**What each button does:**

| Button | What it does |
|---|---|
| **Get (USB)** | Copies every `.txt` file from the stick's `FLICPrograms` folder into the MCU's own Program folder, replacing files of the same name, and refreshes the list: "Move complete. N program files moved." The files stay on the MCU, so next time you can load them without the stick. |
| *(tapping a file)* | Shows its contents in the preview |
| **Refresh** | Reads the list of files on the MCU again |
| **Delete** | Deletes the chosen file from the MCU, after asking. The copy on the stick is untouched. |
| **Load** | Reads the chosen file and makes it the Program to run |

### When the file is good

The status bar says "Custom program loaded." and the Program page opens with the Program as the MCU understood it: start and end time, duration, the default settings, and each DFM's Intervals with the time each is due to start. Read it: this is exactly what will run, and it is saved with the data as `Program.txt`.

Each Interval reads, for example, `(10/25/2026 09:30:00) Dark On,20,-1,20,-1,…,F:40,P:8,D:500,L:0,M:0,360.0min.`: its start, dark running, the twelve thresholds, then (from 2.0.0) the frequency, pulse width, decay, delay and maximum time on, and its length.

### When the file has a problem

- **1.0.7 to 3.5.0:** the status bar says only "Problem loading program." Nothing says which line is wrong. Many mistakes don't stop the load at all: they are ignored, and the Program runs without them. [Section 13.9](#139-mistakes-and-what-each-version-does) lists what each version does with each mistake. Always read the Program page after loading.
- **3.5.1 and 3.5.2:** the status bar names the line and the problem for a few seconds, for example `Problem loading program: line 12: OptoPW 30 ms is not shorter than one period at 40 Hz (25.0 ms)`. Note it down: it isn't shown anywhere else.
- **In every version,** a failed load replaces whatever was loaded with a simple 3-hour recording with every LED off, starting at the next minute. Check the Program page before you press **Run Program**.

### The compatibility check

Once the file loads, the MCU checks it against the DFMs it found:

- **1.0.7:** no check.
- **2.0.0 and 3.5.0:** if a 1.0.5 board's Intervals have a time above 65,535 ms, a **Compatibility Check** box warns: "Version 1.5 DFM are not compatible with decay, delay, or maxtime values > 65536!" It is only a warning: the Program still runs, and that board runs different times from the ones written. Nothing checks the other settings a 1.0.5 board would misread ([section 13.5](#135-how-the-leds-respond)).
- **3.5.1 and 3.5.2:** a **Compatibility Check** box lists each board that can't run the Program and why, for example `DFM 7 (firmware 1.0.5) can't run: non-feeding activation (OptoPW above 30000) needs firmware 2.0.0`, or `DFM 9 runs firmware 4.0.0, which needs PyMCU 4.0.0 or later`. The Program won't start until the board is unplugged or the Program changed.

A DFM that is connected but has no section in the Program records with every LED off (in 3.5.2, unless the Program has an `ID: All` section). Sections for DFMs that aren't connected are dropped. Find the DFMs ([section 6](#6-step-1-find-the-dfms)) before you load a Program.

## 10. Step 5: Set the start time and run

### The start time

A Program file's `StartTime` setting sets the start when the file loads. Without one, the Program starts at the beginning of the next minute after loading. The first line of the Program description, **Start Time**, always shows the start that will be used, seconds included.

You can change it on the Program page:

| | 1.0.7 and 2.0.0 | 3.5.x |
|---|---|---|
| **Now** | Sets the start to the next minute | Sets the start to the next minute. In 3.5.0 and 3.5.1 it is exactly one minute after you press it, which can fall partway through a minute; 3.5.2 uses the start of the next whole minute. |
| Another time | Tap the date and time box beside **Now** and change the month, day, year, hour or minute | Press **Set**, tap a day on the calendar, set the hour and minute with the large − and + buttons, and press **Set Start** |

The start time box doesn't change when you load a Program file, so after **Load** it can still show an earlier time. The description's Start Time is the one that counts.

If you loaded a Program some time ago, press **Now** before **Run Program**: a start time that has already passed starts the recording at once, but it still ends at the original end time, so the recording would be shorter than planned.

### Run Program

**Do:** press **Run Program**.

**What happens, in order:**

1. **From 3.5.1, the Program is checked again** against every DFM, because a board may have been swapped since the Program was loaded. If any board can't run it, a **Program not started** box lists them and nothing starts.
2. **The MCU gets ready.** Most buttons lock, the button changes to **Stop Program**, the Live Data page opens and the status bar says "Staging program."
3. **In 1.0.7 to 3.5.1, the baseline is measured now** (with `Baseline: Yes`): each Well's first 10 readings after you press **Run Program**, a few seconds of signal, are averaged. If the start time is hours away, the baseline is still the one from now. Recording can't start until the baseline is done. In 3.5.2 nothing is measured yet, and until the start time only the DFM on screen is read, so you can still watch it.
4. **At the start time, recording begins.** For every board, the MCU:
    - clears its messages and posts "Recording started";
    - tells each DFM to reset its record counter, so the recording starts clean;
    - sends each DFM its Linkage;
    - creates the recording folder, `FLICData/<MCU name>_<MM_DD_YYYY_HH_MM>`, writes `Program.txt` into it and opens one data file per board;
    - turns each board's button green and starts reading every board, not just the one on screen.
5. **Each DFM is sent its first Interval.** In 1.0.7 to 3.5.1 this happens at the start time. In 3.5.2, with `Baseline: Yes`, each Well's first 10 records of the recording (2 seconds) are averaged first, so every recording starts with a few seconds of dark, even with always-on Wells. Each threshold is then set that far above its Well's own resting level, so a threshold of 20 means "20 above where this Well rests". From then on the DFM runs the light rule by itself. When an Interval ends, the MCU sends the next one, and tries again if the DFM doesn't acknowledge it.
6. **Records are collected.** Every 4 seconds (6 seconds in 1.0.7) the MCU asks each board for the records it has made since the last time, and acknowledges the ones that arrived intact. The DFM sends any others again.
7. **Records are written.** Every few minutes each board's records are added to its data file, and `Messages.csv` is updated. After 12 hours a new data file is started (`DFM1_1.csv`, then `DFM1_2.csv` …).

### Stopping

The Program stops by itself at its end time. To end it early, press **Stop Program**. Either way:

1. Every board is read one last time, the remaining records are written, the files are closed and "Recording ended" is posted.
2. The MCU tells every DFM to switch all its LEDs off.
3. The buttons unlock and the button reads **Run Program** again.

## 11. Step 6: Watch the experiment

### On the Live Data page

- Every board's button should be green.
- **Dark Mode**, **Frequency**, **Pulse Width** and **Optostate** show what the DFM on screen is doing.
- During a recording the display updates each time the board is read, every 4 seconds (6 in 1.0.7). Tick **Fast updates** to read every board about three times a second instead, for a smooth live view. It doesn't change what is recorded: every record is collected either way. It can only be ticked during a recording and switches off when the Program ends.

### On the Messages page

Each line reads `(number) date time -> board <- message (type)`. The board is the DFM's ID, 99 for the Environmental Monitor, or 0 for the MCU itself.

The page shows only Errors and markers (type `Unknown`), and at most the first 100 of them; after that it says "Max messages displayed. Check file for details." Notices, such as a board not answering or a DFM's error code, aren't shown; those that arrive during a recording are saved in `Messages.csv`. The list holds 500 messages per recording; the last says "Reached max messages", and later ones are dropped, from the file too. The list is cleared when DFMs are found or cleared and when a recording starts.

| Message | Type | Meaning |
|---|---|---|
| Recording started, Recording ended, DFM 3 found, Environmental monitor found | Unknown | Markers, not problems |
| `(1234) Skipped index: (1230)` | Error | The DFM's records jumped from Index 1230 to 1234, so the records between were lost, or the DFM restarted |
| `(1230) Repeated index: (1234)` | Error | 2.0.0 (builds from September 2024) and 3.5.x: the DFM sent records that were already saved. The copies were dropped; nothing is lost. |
| `(3) Data queue full` | Error | The MCU couldn't keep up with DFM 3's records |
| Copying data, do not remove USB. Copying complete. | Unknown | Markers from **Export Data** |
| Copy failed! | Error | The export didn't finish ([section 12](#12-step-7-get-the-data-off-the-mcu)) |
| Create directory failed; `(3) Data file write failed: …` (3.5.x) | Error | The data can't be saved: check the MCU's free storage |
| `DFM 7 (firmware 1.0.5) can't run this Interval: …` | Error | 3.5.1 and 3.5.2: a board turned out, after the start, to have firmware that would misread this Interval. It wasn't sent, and the DFM keeps its previous settings. |

### What the system survives

| What happens | Effect |
|---|---|
| The MCU is busy, or a reply is damaged | Nothing lost. The DFM keeps its records until they are acknowledged and sends them again. In 1.0.7 (and 2.0.0 builds before September 2024) a resent record can be written twice, with the same `Index`. |
| The bus is disconnected briefly | Nothing lost: the light keeps following the flies, and when the bus is back the DFM sends what it stored. |
| The bus is disconnected for longer | The DFM's store fills and the oldest records are overwritten. The data file has a gap in its `Index` column and Messages reports "Skipped index". An Interval change due during the outage happens when the bus is back. |
| A DFM loses power and restarts | Its record counter starts again at 1 and its LEDs stay off until the next Interval starts. In 1.0.7 its new records are written with times that start again from the beginning of the recording. From 2.0.0 its new records are dropped as "Repeated index" until its counter passes where it was, which takes as long as the recording had run. Stop the Program and start a new recording. |
| The MCU loses power | The recording stops, and the records collected since the last write, up to a few minutes, are lost. The DFMs keep running their last Interval's light rule, unrecorded. Power the MCU on, **Find DFM** and start a new recording; it goes in a new folder. |

## 12. Step 7: Get the data off the MCU

### Export Data

**Do:** plug in a USB stick (with 3.5.x, one with a `FLICData` folder), press **Export Data**, read the warning and press **Okay**. Wait for the status bar to say the stick is unmounted before removing it.

**What it does:** copies every recording on the MCU, not just the last, into the stick's `FLICData` folder, replacing files of the same name. The Messages page opens and the status bar shows the progress.

| | 1.0.7 and 2.0.0 | 3.5.x |
|---|---|---|
| The stick | The first stick found. `FLICData` is created if it isn't there. | The first stick with a `FLICData` folder; otherwise "No USB with a FLICData folder found." |
| When it's done | "Data copy complete.", then the stick is unmounted: "USB unmounted. Ready to remove." | Everything is written to the stick, then it is unmounted: "Data copy complete. USB unmounted, ready to remove." |
| If it fails | "Data copy failed." | The reason is shown, for example "Data copy failed: No space left on device", and the stick stays mounted, so you can try again |
| If you press Cancel | The stick is unmounted anyway. Unplug it and plug it in again to use it. | The stick stays mounted |

Export is locked while a Program runs.

### Delete Data

**Do:** after the data is safely on a stick and checked, press **Delete Data** and confirm twice.

**What it does:** deletes every recording on the MCU, to free its storage. It can't be undone.

### The recording folder

Each recording is one folder, named after the MCU and the start time, for example `FLICMCU_10_25_2026_09_30`:

| File | Contents |
|---|---|
| `DFM<ID>_0.csv` | One per DFM: one row for every 200 ms. After 12 hours a new file, `_1`, then `_2` … Join them in order. |
| `EnvMon_0.csv` | The Environmental Monitor's readings, if present |
| `Messages.csv` | Every message of the recording, Notices included: `DFM,Date,Time,Millisecond,Sample,Message,MsgType` |
| `Program.txt` | The Program as the MCU understood it, as shown on the Program page |

### The data file

Every version writes the same 27 columns:

| Column | Meaning |
|---|---|
| `Date`, `Time` | When the record was taken, on the MCU's clock (`MM/DD/YYYY`, `HH:MM:SS`). Computed as the recording's start plus `Index` × 200 ms, so consecutive records are exactly 200 ms apart. |
| `MSec` | Milliseconds past `Time` |
| `Sample` | Record number within the recording, from 1. It continues across the 12-hour files. |
| `W1`–`W12` | Each Well's signal, 0 to 1023, in Well order 1A, 1B, 2A … 6B. Raw, **not** baseline-subtracted, even with `Baseline: Yes`. With DFM firmware 2.0.0 and later, a value above 65,536 means the Well was in training during that record: subtract 65,536 for the signal. |
| `Temp`, `Humid`, `LUX` | °C, % relative humidity and lux from the Environmental Monitor. 0 without one. |
| `VoltsIn` | The DFM's supply voltage |
| `Dark` | 1 when the DFM was running dark, 0 when not |
| `OptoFreq`, `OptoPW` | LED pulse frequency (Hz) and pulse width (ms) in force |
| `OptoCol1` | Which LEDs were lit at the instant the record was taken, as a bit mask: bit 0 is Well 1, bit 11 is Well 12. An on-period shorter than 200 ms may not show. |
| `OptoCol2` | A second LED-state field, used only by older DFM types |
| `Error` | The DFM's error flags, as on the DFM Indicators ([section 7](#7-step-2-check-each-dfm-on-the-live-data-page)). 0 means none. |
| `Index` | The DFM's own record counter, from 1 at the start of the recording. A gap means records were lost. In 1.0.7 files, drop rows that repeat an `Index`. |

### Analysing the data

The lab's analysis software, pyflic, reads these 27-column files, including the training flag in the Well columns. Put the `DFM<ID>_<n>.csv` files, `Program.txt` and `Messages.csv` in the experiment's `data` folder. pyflic's own help (F1, or `pyflic help`) explains the rest.

## 13. Program file reference

This is the Program file format for PyMCU 1.0.7 to 3.5.2. It is the format of the 2022 *Stand Alone MCU Programming Conventions*, with what 2.0.0 and 3.5.x added. Version 4.0 reads most of these files too, but describes them in its own documents.

### 13.1 How a file is laid out

A Program is a plain text file divided into sections. Each line is one of:

| Line | Example |
|---|---|
| A section heading, in square brackets | `[General]` |
| A setting, written `Name: value` | `ExpDurationMin: 120` |
| A comment, starting with `#` | `# Choice chambers, B wells only` |
| Blank | |

- A Program has up to three kinds of section: `[General]` for the whole experiment and the defaults for every DFM, `[DFM]` for one DFM, and `[EnvMon]` for the Environmental Monitor.
- Section and setting names can be written in any case: `[general]`, `EXPDURATIONMIN` and `expDurationMin` all work. Spaces around values don't matter.
- Put each comment on a line of its own. A comment after a value becomes part of the value, which usually stops the load.
- Settings take whole numbers, except the length of an Interval, which may have decimals.

### 13.2 The [General] section

| Setting | Meaning | Default |
|---|---|---|
| `StartTime` | When recording starts, on a 24-hour clock: `HH:MM:SS` for today, or `MM/DD/YYYY HH:MM:SS` for another day. `HH:MM` alone isn't accepted. | The start of the next minute after loading |
| `ExpDurationMin` | How long recording lasts, in whole minutes. `0` means as long as the longest DFM's Intervals. **Always set it**: without it, recording lasts 1 minute. | 1 |
| `ProgramType` | How each DFM steps through its Intervals: `Linear`, `Repeating`, `Circadian` or `Constant` ([section 13.6](#136-program-types)) | `Linear` |
| `OptoFrequency` | How many times per second an LED pulses while it is on, 1 to 500 Hz | 40 |
| `OptoPW` | How long each pulse lasts, in ms. It must be shorter than one period (1000 ÷ `OptoFrequency` ms). | 8 |
| `OptoDecay` | In ms: how long an LED stays on after contact ends, or the length of each light period, depending on the rule ([section 13.5](#135-how-the-leds-respond)) | 0 |
| `OptoDelay` | In ms: the lockout in fixed interval, and part of the firmware 2.0.0 rules | 0 |
| `MaxTimeOn` | In ms: the longest an LED can stay on in one period in closed loop. 0 means no limit. | 0 |
| `Linkage` | 12 whole numbers, one per Well. Wells with the same number light together ([section 13.7](#137-linkage)). | `1,2,3,4,5,6,7,8,9,10,11,12` (no linkage) |
| `Baseline` | `Yes` measures each Well's resting signal at the start, and thresholds are measured from it. Anything else means no baseline. | `Yes` |

- `StartTime`, `ExpDurationMin` and `Baseline` can only be set in `[General]`. They apply to every DFM.
- A `StartTime` of `HH:MM:SS` that has already passed today starts the recording as soon as you press **Run Program**, and it ends at the start time plus `ExpDurationMin`.
- Times (`OptoDecay`, `OptoDelay`, `MaxTimeOn`) can be up to 65,535 ms on a 1.0.5 board. With PyMCU 2.0.0 and later and firmware 2.0.0 and later they can be up to 4,294,967,295 ms.

This section starts recording at 1:13 AM and records for 2 hours, with 30 Hz pulses of 8 ms, a half-second decay, a 2.5-second limit on each light period, and Wells 2 and 3 linked:

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

### 13.3 The [DFM] section

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
|---|---|
| `ID` | Required, and first: the number set on the DFM's dials, 1 to 98 |
| `ProgramType`, `Linkage` | Override the `[General]` values for this DFM |
| `OptoFrequency`, `OptoPW`, `OptoDecay`, `OptoDelay`, `MaxTimeOn` | Override the `[General]` values for this DFM. Put them before the Interval lines: each Interval uses the values set above it. |
| `Interval` | One step of the program. Intervals run in the order written. |

With the `[General]` section above, this DFM runs dark for 2 hours with each LED lit when its Well is 20 above its resting level; then for 2 hours with its indicator LEDs on and every OptoLid LED off; then dark with every OptoLid LED on until the end of the recording.

**`ID: All`** (3.5.2 only) in place of a number makes the section apply to every connected DFM that has no section of its own. Earlier versions refuse the file.

Give each DFM only one section: a second section for the same ID replaces the first without warning.

### 13.4 Interval lines

```
Interval: dark, 1A, 1B, 2A, 2B, 3A, 3B, 4A, 4B, 5A, 5B, 6A, 6B, minutes
```

An Interval line has 14 numbers, separated by commas:

1. **Dark running:** `1` turns off the DFM's indicator LEDs, `0` leaves them on. Nothing else is accepted.
2. **Twelve thresholds,** one per Well, in the order 1A, 1B, 2A, 2B … 6A, 6B. Each one is:
    - `0`: the LED is always on.
    - `-1`: the LED is never lit by this Well. Any value above 1023 also means this.
    - A signal level from 1 to 1023: contact means the signal is above it. With `Baseline: Yes`, the level is measured from the Well's resting signal. 20 is a common choice.
3. **Length** in minutes. It may have decimals: `0.5` is 30 seconds.

**From 2.0.0,** an Interval can have its own opto settings: add five numbers between the thresholds and the length, `OptoFrequency`, `OptoPW`, `OptoDecay`, `OptoDelay` and `MaxTimeOn`, for 19 numbers in all. For example, 10 Hz pulses with a 1-second decay for 30 minutes:

```
Interval: 1,20,20,20,20,20,20,20,20,20,20,20,20,10,8,1000,0,0,30
```

PyMCU 1.0.7 skips a 19-number line without warning, so the Program loads without that Interval. Read the Program page after loading.

### 13.5 How the LEDs respond

Each Well's threshold and the opto settings decide when its LED is on. While an LED is on, it pulses at `OptoFrequency` with pulses of `OptoPW` ms.

**On every firmware:**

| Rule | How to ask for it | What the LED does |
|---|---|---|
| **Always on** (open loop) | Threshold `0` | On for the whole Interval, whatever the fly does |
| **Always off** | Threshold `-1` | Never lit by this Well. Linkage can still light it. |
| **Closed loop** | A threshold from 1 to 1023, and `OptoDelay: 0` | On while the signal is above the threshold, and for `OptoDecay` ms after it falls below. `MaxTimeOn` above 0 limits one on-period, `OptoDecay` included. |
| **Fixed interval** | A threshold, `OptoDelay` above 0 and `MaxTimeOn: 0` | Contact starts a light period of exactly `OptoDecay` ms. A new one can't start until `OptoDelay` ms after the previous one started. |

- In closed loop, an `OptoDecay` of 500 to 1000 ms stops the LED flickering while the fly's proboscis moves in and out of the food. Once `MaxTimeOn` has turned an LED off, it can light again after the signal has stayed below the threshold for `OptoDecay` ms.
- In fixed interval, set `OptoDecay` above 0 (a 1.0.5 board uses 1000 ms when it is 0) and make `OptoDelay` longer than `OptoDecay`. For example, `OptoDecay: 1000` with `OptoDelay: 60000` gives a feeding fly 1 second of light, and at most one such second per minute.

**On DFM firmware 2.0.0 and later, with PyMCU 2.0.0 and later:**

| Rule | How to ask for it | What the LED does |
|---|---|---|
| **Non-feeding activation** | `OptoPW` = 32768 + the pulse width (32776 for 8 ms), and `OptoDecay` above 0 | Off during contact. After `OptoDelay` ms without contact, on for `OptoDecay` ms, repeating while the fly stays away. A Well that is touched stays dark until `OptoDelay` ms after contact ends. |
| **Progressive ratio** | `OptoDelay` and `MaxTimeOn` both above 0, and `OptoDecay` above 0 | The first contact lights the LED for `OptoDecay` ms. Each later Activation needs `OptoDelay` ms more accumulated contact than the last, up to `MaxTimeOn`. Contact adds up across touches; only a new Interval starts it again. |
| **Training, then progressive ratio** | `OptoFrequency` = count × 512 + the frequency (1576 is 3 Activations at 40 Hz; count up to 127), with progressive ratio | For the first `count` Activations of each Well, any contact lights the LED, holding keeps it on, and it stays on `OptoDecay` ms after release. Then progressive ratio starts, and its first Activation needs `OptoDelay` ms of contact. A new Interval starts training again. DFM firmware 3.5.1 built before the training-count fix gives one Activation fewer than the count. |

For example, `OptoDecay: 2000`, `OptoDelay: 1000` and `MaxTimeOn: 5000` give a fly holding the food 2 seconds of light at once, then 2 seconds of light after further contact of 1, 2, 3, 4, 5, 5 … seconds.

**On a 1.0.5 board, these three rules don't exist.** The board misreads them without warning: it cuts a non-feeding pulse width down to one period, cuts a training frequency down to its maximum, and runs progressive ratio as fixed interval, ignoring `MaxTimeOn`. (The 2022 conventions described `OptoDelay` with `MaxTimeOn` as a hold-off after each light period; a 1.0.5 board runs fixed interval instead.) What each version does about it:

| PyMCU | A 1.0.5 board is sent a firmware 2.0.0 rule, or a time above 65,535 ms |
|---|---|
| 1.0.7 | Sent as written and misread. 1.0.7 can't send times above 65,535 ms correctly to any board. |
| 2.0.0, 3.5.0 | Sent as written and misread. Long times give a warning when the Program loads ([section 9](#the-compatibility-check)). |
| 3.5.1, 3.5.2 | Refused: the Program won't start while that board is connected |

**3.5.2 also refuses,** for every board, progressive ratio or non-feeding activation with `OptoDecay: 0` (the DFM would light each Activation for 1 ms) and a training count with any rule but progressive ratio (the DFM would ignore it).

### 13.6 Program types

| Type | Behavior |
|---|---|
| `Linear` | Runs the Intervals in order, then stays in the last one until recording ends |
| `Repeating` | Goes back to the first Interval after the last, until recording ends |
| `Circadian` | Repeats on the clock: the Intervals must add up to exactly 1440 minutes (24 hours), and the first starts at midnight. A total other than 1440 stops the load. |
| `Constant` | Meant to run only the first Interval. **It doesn't work in these versions:** the DFM is never sent the Interval, and in 1.0.7 and 2.0.0 PyMCU can close at the start time. Use `Linear` with a single Interval instead; it does the same. |

A `ProgramType` value that isn't one of these four, a misspelling for example, is read as `Constant` without warning, in every version. Check the Program page after loading.

Recording time always takes precedence. If `ExpDurationMin` is shorter than a DFM's Intervals, recording ends partway through them. If it is longer, a Linear program stays in its last Interval until the end.

### 13.7 Linkage

Linkage lights LEDs together. Wells with the same number form a group, and every LED in a group is on whenever any Well in it lights its LED.

Its most common use is a choice chamber, in which one fly has two Wells, A on the left and B on the right. This section lights both LEDs in a chamber only when the fly feeds from the B Well. It also sets 10 Hz pulses for this DFM alone:

```
[DFM]
ID: 1
ProgramType: Linear
OptoFrequency: 10
Linkage: 1,1,3,3,5,5,7,7,9,9,11,11
Interval: 0,-1,20,-1,20,-1,20,-1,20,-1,20,-1,20,120
```

Linkage can also give control flies exactly the same light as treatment flies: set the control Wells' thresholds to `-1` and give them the linkage number of a treatment Well.

A `Linkage` line without exactly 12 numbers is ignored without warning.

### 13.8 The [EnvMon] section

The `[EnvMon]` section controls the Environmental Monitor's two relays and four output pins, which can switch external devices.

```
[EnvMon]
ID: 99
ProgramType: Linear
Interval: 0,1,0,1,1,0,0,0,0,0,0,0,0,120
Interval: 1,0,0,0,0,1,1,0,0,0,0,0,0,120
```

**Start it with `ID: 99`.** The 2022 conventions said no ID was needed, but these versions need the line: without it, 3.5.1 and 3.5.2 ignore the section, and 1.0.7 to 3.5.0 add its Interval lines to the `[DFM]` section above it.

Each Interval line has 14 numbers:

1. **Dark running:** `1` turns off the indicator LEDs, `0` leaves them on.
2. **Relay 1, Relay 2, Output 1, Output 2, Output 3, Output 4:** `1` is on, `0` is off.
3. **Six numbers that are ignored.** Write them as `0`.
4. **Length** in minutes.

In this example, for the first 2 hours Relay 1 and Outputs 1 and 2 are on. After that, both relays and Outputs 1 and 2 are off, Outputs 3 and 4 are on, and the indicator LEDs are dark until recording ends.

### 13.9 Mistakes and what each version does

Because 1.0.7 to 3.5.0 don't say why a file failed, and no version reports every mistake, check each file against this table and read the Program page after loading.

| Mistake | 1.0.7 to 3.5.0 | 3.5.1 and 3.5.2 |
|---|---|---|
| A misspelled section or setting name | Ignored: the setting keeps its default | Ignored |
| A line without a colon | Ignored | Ignored |
| A word, or a decimal, where a whole number is needed (`ExpDurationMin: 90.5`) | Load fails | Load fails, line named |
| An Interval line with the wrong count of numbers | 1.0.7: the line is skipped. 2.0.0 and 3.5.0: load fails. | Load fails, line named |
| Dark running other than `0` or `1` | Load fails | Load fails, line named |
| A `StartTime` in neither form | Load fails | Load fails, line named |
| A misspelled `ProgramType` | Read as `Constant` | Read as `Constant` |
| `Linkage` without 12 numbers | Ignored | Ignored |
| `Baseline` other than `Yes` | No baseline | No baseline |
| Circadian Intervals that don't add up to 1440 minutes | Load fails | Load fails, DFM named |
| `OptoFrequency` outside 1 to 500 (other than the training form), `OptoPW` not shorter than one period, negative times | Sent to the DFM as written | Load fails, line named |
| `ID: All` | Load fails | 3.5.1: load fails, line named. 3.5.2: accepted. |
| The same DFM ID in two sections | The second replaces the first | The second replaces the first |
| Settings before a section's `ID` line | Added to the section above, or ignored | Ignored |
| `ExpDurationMin` left out | Recording lasts 1 minute | Recording lasts 1 minute |

## 14. Settings and maintenance

### About

Press **About** for:

- the MCU's name: "Flidea Master Control Unit (V3)", with the Pi model from 2.0.0, for example "(V3; P5)";
- the PyMCU version;
- its network address (IP), for remote support;
- free storage;
- from 3.5.0, the clock: on a Pi 5 its battery, for example "Clock battery: 2.95 V, OK"; on a Pi 4 (3.5.1 and 3.5.2) "Clock: DS3231 module".

**Settings** opens the Settings page. It is locked while a Program runs.

### Settings

| Setting | Versions | What it does |
|---|---|---|
| **Set Date and Time** | All | Sets the MCU's clock and saves it to the battery-backed clock, so it is kept while the MCU is off. In 1.0.7 and 2.0.0 it opens one large date and time box; change it and press **OK**. In 3.5.x it opens a calendar with − and + buttons for the hour and minute; press **Set Time**, and the status bar confirms "Clock set to …". |
| **Update MCU** | All | Installs a PyMCU update from a USB stick (below) |
| **Use Dark Theme** | 2.0.0 (builds from December 2024) and 3.5.x | Light text on a dark background, from the next start |
| **Screen off after** | 3.5.x | How long the screen stays on without a touch: − and + step from Never through 15 seconds to an hour. A touch wakes it. |

### Updating PyMCU

Updates never change recorded data or saved Programs.

**1.0.7 and 2.0.0:**

1. Put the update file (`.tgz`) in a folder named `FLICUpdates` on a USB stick, with no other `.tgz` file there.
2. Plug the stick in, press **About**, then **Settings**, then **Update MCU**.
3. The status bar says "Updating...", then "Update complete. Rebooting. Remove USB." and the MCU restarts. "Update failed." means there was no update file, or more than one.

The file isn't checked before it is installed, so use only update files from the lab.

**3.5.x:**

1. Copy the update file (`.mcu`) as it is onto a USB stick, at the top level or in a folder named `FLICUpdates`. Put only one update file on the stick.
2. Plug the stick in ("USB connected..."), press **About**, then **Settings**, then **Update MCU**.
3. Check the version and confirm. The box shows the new version beside the installed one, for example "Install PyMCU 3.5.2 from PyMCU_3.5.2.mcu? Installed now: 3.5.1. The MCU restarts when the update is done."
4. Wait. The status bar shows "Updating to 3.5.2... do not remove USB or power." The MCU restarts by itself.
5. After the restart, remove the stick and check the version under **About**.

If anything goes wrong, the status bar says "Update not started: …" or "Update failed: …", and the MCU keeps the version it had. An older `.mcu` file goes back to that version the same way. The update notes for 3.5.x are in `docs/Updating.md` at tag `v3.5.2` in the PyMCU repository.

### Logs

3.5.x keeps a log at `~/PyMCU/mcu.log`, which lab staff can read remotely.

## 15. Troubleshooting and known problems

| Problem | Likely cause | What to do |
|---|---|---|
| PyMCU doesn't open after power-on (1.0.7 and 2.0.0) | Less than 1 GB of free storage: these versions fail at start-up instead of warning | Lab staff copy the old recordings off over the network, then delete them from the MCU's `FLICData` folder |
| "No DFMs found." | Boards not powered or still starting, bus cable loose, or IDs outside 1 to 98 | Check power and cable, wait a few seconds after power-on, press **Find DFM** again |
| A DFM is missing or has the wrong ID | Two boards share an ID, or the dials were changed without a restart | Give every board its own ID and power-cycle it |
| PyMCU closes at **Find DFM** (2.0.0) | An Environmental Monitor is on the bus | Unplug the monitor, or use 1.0.7 or 3.5.x |
| A DFM's button is blue (Miss) | The board stopped answering | Check its power and cable |
| A DFM records, but its LEDs never follow the Program, and P Size is ticked | Its firmware is newer than this PyMCU instructs ([section 4.1](#41-dfms)) | Update PyMCU, or use the board only for recordings without light |
| "Problem loading program." | A mistake in the file. 1.0.7 to 3.5.0 don't say which. | Check the file against [section 13.9](#139-mistakes-and-what-each-version-does); 3.5.1 and later name the line |
| The Program loads but runs differently from the file | A mistake that is ignored rather than refused: a misspelled setting, a misspelled `ProgramType`, a 19-number Interval in 1.0.7 | Read the Program page; see [section 13.9](#139-mistakes-and-what-each-version-does) |
| The recording lasts 1 minute | `ExpDurationMin` is missing or misspelled | Add it to `[General]` |
| The Compatibility Check lists a DFM (3.5.1 and 3.5.2) | Its firmware can't run part of the Program | Unplug the board, or change the Program ([section 13.5](#135-how-the-leds-respond)) |
| LEDs don't come on | The threshold is too high, the Wells are `-1`, the DFM isn't in the Program, the Program type is `Constant`, the OptoLid is unplugged, or (3.5.2) the first few seconds of baseline | Check the Program page, test with **Outputs** |
| LEDs are on all the time | Always-on Wells, a threshold too low, or `Baseline: No` with high resting signals | Check the Program page and the plot |
| The baseline seems wrong (1.0.7 to 3.5.1) | It was measured when **Run Program** was pressed, which may be long before the start | Press **Run Program** close to the start time, with the flies settled |
| "Skipped index" messages | Records were lost: the bus was disconnected too long, or a DFM restarted | Check the bus cable and the DFMs' power |
| No Ack, ID Ack or I2C ticked now and then | A reply or acknowledgement was missed and resent | Normal; nothing lost |
| Export Data does nothing (3.5.x): "No USB with a FLICData folder found." | The stick has no `FLICData` folder | Create it at the top level of the stick |
| The stick can't be used after a cancelled export (1.0.7 and 2.0.0) | These versions unmount the stick even when the export is cancelled | Unplug it and plug it in again |
| Export Data or Update MCU is greyed out | No stick, or a Program is running | Plug in the stick; wait for the Program to end |
| The time is wrong after a power-off | The clock battery is flat or missing | Set the time in Settings; replace the battery |

## 16. Appendix: the versions side by side

| | 1.0.7 | 2.0.0 | 3.5.0 | 3.5.1 | 3.5.2 |
|---|---|---|---|---|---|
| Runs on | Pi 4 or earlier | Pi 5 | Pi 5 | Pi 4 or 5 | Pi 4 or 5 |
| Instructs DFM firmware | 1.0.5 | 1.0.5, 2.0.0 | 1.0.5 to 3.5.x | 1.0.5 to 3.5.x | 1.0.5 to 3.5.x |
| Firmware shown on the DFM page | No | Yes | Yes | Yes | Yes |
| Error box labels | Fixed | Fixed | By firmware, with Overflow | By firmware | By firmware |
| Environmental Monitor | Works | Can close PyMCU | Works | Works | Works |
| Start time | Date and time box, **Now** | Date and time box, **Now** | **Now**, **Set** (calendar) | **Now**, **Set** | **Now**, **Set**, always on the whole minute |
| Program mistakes reported | "Problem loading program." | Same | Same | Line named | Line named, more checks |
| 19-number Interval lines | Skipped | Yes | Yes | Yes | Yes |
| Firmware 2.0.0 rules (non-feeding, progressive ratio, training) | No | Yes | Yes | Yes | Yes |
| `ID: All` | No | No | No | No | Yes |
| Compatibility check | None | Warning for long times | Warning for long times | Refuses, with reasons | Refuses, with reasons |
| Baseline measured | At **Run Program** | At **Run Program** | At **Run Program** | At **Run Program** | First 2 s of recording |
| Records collected every | 6 s | 4 s | 4 s | 4 s | 4 s |
| Resent records | Written twice | Dropped (builds from September 2024) | Dropped | Dropped | Dropped |
| Export Data | Any stick, always unmounts | Same | Needs `FLICData`, unmounts after a successful copy | Same | Same |
| Updates | `.tgz` in `FLICUpdates` | Same | Checked `.mcu`, reversible | Same | Same |
| Dark theme | No | Builds from December 2024 | Yes | Yes | Yes |
| Screen-off setting | No | No | Yes | Yes | Yes |
| Low storage at start-up | PyMCU doesn't open | PyMCU doesn't open | Warning | Warning | Warning |
| Recording status label | Record | Record | Record | Record | Rec |
