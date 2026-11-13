# Ratio Paradigms can count Contact as well as Events

ADR 0001 made progressive ratio and fixed ratio count Events. That left no way to repeat an experiment run on firmware 3.5.2, whose progressive ratio counted milliseconds of Contact: a Step in Events can only approximate a Step in time. In the Jove and Tahrim female recordings (pyflic `test_data`), the Event-counted rewrite with Step 5 cost about ten times the old program's contact per Activation, and breaking points fell from a median of 10–45 to 4–7. So from DFM firmware 4.1.0 a ratio Paradigm has a `Counter`: `Events` (the default, unchanged) or `Contact`.

With `Contact`, Progress counts the milliseconds of Contact outside the Well's own Activation, added up across bouts. Contact that carries on after an Activation ends counts, and the Activation starts the moment the sum reaches the Requirement. That is the 3.5.2 rule, so `FirstRequirement` = `Step` = the old `OptoDelay` repeats a 3.5.2 program exactly.

The Requirement and Progress fields of the Status record are 16-bit, and in milliseconds they would stop at 65.5 s, which strong responders on 1 s steps pass. The firmware therefore counts in units of 10 ms (655 s per Activation), and the 127-byte record is unchanged. Programs state milliseconds in multiples of 10; PyMCU sends tenths and writes milliseconds to the data file.

## Consequences

- The counter travels as bit 1 of the Paradigm instruction's flags. Firmware 4.0.0 ignores flags it doesn't know and would count Events, so PyMCU refuses `Counter: Contact` on 4.0.0 boards at the Compatibility Check and again when the Interval is sent. Firmware 4.1.0 NACKs any flag bit it doesn't know, so a later flag can't be silently ignored either.
- The keep-state flag keeps a Well's Paradigm state only when the counter is unchanged too.
- ADR 0001's reasons still apply to `Contact`: the count depends on the 270 ms smoothing and the Threshold, and a Well whose signal drifts above its Threshold keeps earning Activations with no fly. `Events` stays the default.
- Old Programs that use progressive ratio are still refused rather than converted. Firmware 2.0.0 to 3.5.1 and 3.5.2 differ in their acclimation count and first activation, so the file alone doesn't say which rewrite is exact. ProgramFormat.md gives both.
- pyflic must read `Counter Contact` in `Program.txt` and treat Requirement and Progress as milliseconds for such a Paradigm.
