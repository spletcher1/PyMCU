# The adaptive baseline is tracked by PyMCU and moves at a limited rate

With `Baseline: Adaptive`, PyMCU follows each Well's resting signal from the Status records it already receives. Each minute it moves the Well's Tracked baseline towards that minute's Floor (10th percentile) by at most `BaselineRatePerHour` (default 5 counts an hour), up or down, within `BaselineCapCounts` (default 50) of the Starting baseline. Every 10 minutes, if a Well's Tracked baseline is 10 or more counts from the Baseline in force, PyMCU sends the running Interval again with new Thresholds, under a new instruction number and with the keep-state flag. PyMCU writes the Baseline in force on every data-file row, from its own record of what each instruction number carried. The firmware is unchanged. The specification is [../adaptive-baseline-plan.md](../adaptive-baseline-plan.md).

The need: the Starting baseline is measured once, in the first 2 s, so if a Well's resting signal drifts, a Threshold of 20 no longer means 20 above rest. Nothing recorded which baseline had been used, so pyflic had to guess it.

The constraint that shaped the estimator: in the 9 recordings (65 DFMs) in pyflic's `test_data`, the sucrose Wells that trigger the light drift at most about 1 to 4 counts an hour and 13 counts a day, but Chrimson flies stay on the lit Well continuously for up to 76 minutes, 80 to 150 counts above the floor. You can't tell a step from drift any sooner than the step lasts, so the tracker limits how fast the baseline moves instead of choosing a window to average over.

## Consequences

- Firmware 4.0.0 needs no change. Its keep-state flag already preserves every Well's Paradigm state when an instruction is repeated with new Thresholds. Each repeat restarts the pulse counters, which cuts one pulse cycle short on a Well lit at that moment, as an Interval change always has.
- Firmware older than 4.0.0 resets its hold, lockout and training state and turns its LEDs off on every instruction (`SetLEDParams` in 3.5.x). It gets the Tracked baseline only with the instruction it receives anyway at an Interval or Cycle change.
- A 76-minute plateau moves the Tracked baseline about 6 counts, which is less than the 10-count step, so nothing is sent and the light follows the fly throughout. Slow drift is followed without lag. A sudden step takes hours to follow and is stopped by the cap, with an error on the Messages page.
- With the 10-count step and the 10-minute check, most recordings of sucrose Wells send no update at all.
- The data file gains `Baseline1`–`Baseline12` (102 fields). They are written for `Baseline: Yes` as well, which removes pyflic's guess at the fixed baseline.
- A same-number resend (a retry, a DFM restart, a record showing another instruction) must carry the Thresholds that number was first sent with. So the Baselines are changed only immediately before a new number is issued, and each number keeps its own copy.

## Considered options

- **The DFM tracks its own baseline.** It has every Scan, but it would need a release that takes margins rather than Thresholds and a longer Status record to report the baseline. The record ring holds 780 × 127 bytes of the PIC32MX795's 128 KB of RAM, so 24 more bytes per record would cut the ring from 2.6 to about 2.2 minutes. Drift takes hours, so 200 ms records are plenty. Rejected.
- **Re-baseline only at Interval or Cycle boundaries.** Simplest, but a 12-hour Interval is never corrected. Kept only for firmware older than 4.0.0.
- **A minimum or low percentile over a long window (hours).** It resists plateaus shorter than the window, but follows upward drift a whole window late. Rejected.
- **A mean that freezes during contact.** It stops updating as soon as drift lifts the resting signal above the Threshold, which is the very case to fix. Rejected.
- **Absorbing long contact as an artefact.** That judges the fly's behaviour. ClosedLoop's `MaxOnMs` is what limits lock-on. Rejected.
- **Correcting a Starting baseline taken during contact faster in the first minutes.** Rejected: starting with no fly on the food is the experimenter's job, and every correction sent should be one that matters.
