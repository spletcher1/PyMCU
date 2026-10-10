# FLIC optogenetics

PyMCU runs experiments on DFMs, feeding monitors with twelve wells. Each well's signal can trigger a light on the OptoLid according to a Program. These terms are shared by Program files, PyMCU, the DFM firmware and the data files.

## Hardware

**DFM**:
A feeding monitor board with twelve Wells and an OptoLid, identified by the number set on its two ID dials.
_Avoid_: Board, slave

**MCU**:
The Raspberry Pi running PyMCU, which runs the Program, polls the DFMs and writes the data files.
_Avoid_: Master, host (in user-facing text)

**Well**:
One of a DFM's twelve feeding sites, named in row-major order 1A, 1B, 2A, 2B, and so on, each with its own LED on the OptoLid.
_Avoid_: Channel

**Environmental Monitor**:
The board with ID 99 that records temperature, humidity and light and switches relays and output pins.
_Avoid_: EnvMon, EVM (in user-facing text)

## Programs

**Program**:
A text file that defines an experiment: when it starts, how long it runs, and the Intervals each DFM steps through.

**Interval**:
A timed step of a DFM's Program that sets dark running, the Thresholds, the Paradigm and the Paradigm's parameters for all twelve Wells.

**Dark running**:
An Interval setting that turns off the DFM's four indicator LEDs. It does not affect the OptoLid.
_Avoid_: Dark mode, dark state

**Cycle**:
One pass through all of a Repeating Program's Intervals; the first pass is Cycle 1.

**Paradigm**:
A named, configured recipe in a Program that decides when a Well's LED turns on. It has a Paradigm type, the light settings and the type's settings, for example "PR10". One Paradigm applies to all Wells of a DFM during an Interval.
_Avoid_: Mode, behavior, inferring the paradigm from which settings are zero

**Paradigm type**:
The rule a Paradigm follows: OpenLoop, ClosedLoop, FixedInterval, NonFeeding, ProgressiveRatio or FixedRatio.
_Avoid_: Schedule (overloaded)

**Threshold**:
The signal level above which a Well counts as in contact with the food. Instead of a Threshold, a Well can be set On or Off for an Interval, whatever the Paradigm.

**Linkage**:
A grouping of Wells whose LEDs turn on together when any Well in the group is turned on.

## Fly behavior

**Contact time**:
The time a Well's signal spends above its Threshold, measured in milliseconds.
_Avoid_: Licks (the DFM does not detect individual licks)

**Event**:
One feeding bout at a Well. It starts when the Well's signal rises above its Threshold, unless an Activation is in progress, and it ends once the signal has stayed below the Threshold for the Event gap. Progressive ratio, fixed ratio and Acclimation count Events.
_Avoid_: Lick, interaction, signal

**Event gap**:
How long a Well's signal must stay below its Threshold before the current Event ends, so a flickering signal is not counted as several Events.

## Optogenetic response

**Activation**:
One LED on-period that a Paradigm starts at a Well. It is not necessarily a reward, because the stimulus can be aversive.
_Avoid_: Reward, trigger, light event

**Hold**:
How long a closed-loop Activation continues after contact ends.
_Avoid_: Decay

**Lockout**:
Under FixedInterval, the time from the start of an Activation during which no new Activation can start.
_Avoid_: Delay, interval (Interval means a Program step)

**Requirement**:
The number of Events a Well must produce for its next Activation under progressive ratio or fixed ratio.
_Avoid_: Lick threshold, ratio threshold

**Series**:
How a progressive ratio's Requirement grows: Arithmetic (a fixed step each time) or Exponential (the Richardson–Roberts series).
_Avoid_: Schedule

**Progressive ratio**:
A Paradigm whose Requirement grows after every Activation, following an arithmetic or exponential series.
_Avoid_: Increasing licks

**Fixed ratio**:
A Paradigm whose Requirement stays the same for every Activation.

**Acclimation**:
A Phase that can precede any Paradigm, during which a Well's LED follows simple closed-loop rules so the fly learns the association. It ends for each Well separately once that Well has had a set number of Activations.
_Avoid_: Training, pre-training

**Phase**:
Where a Well is in its Interval's sequence: Acclimation or Main.

## Data

**Status record**:
The snapshot a DFM reports for every 200 ms: Well signals, LED state and the Paradigm state of each Well.
_Avoid_: Packet (that is the transport unit)
