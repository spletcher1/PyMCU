# Ratio Paradigms count Contact by default

From PyMCU 4.0.1, a ProgressiveRatio or FixedRatio Paradigm without a `Counter` line counts milliseconds of Contact: the progressive ratio of DFM firmware before 4.0.0, which DFM firmware 4.0.1 runs again ([0005](0005-ratio-paradigms-can-count-contact.md)). `Counter: Events` keeps the Event counting of firmware 4.0.0. ADR 0005 had kept `Events` as the default. This reverses that, at the lab's request (15 November 2026): Event-counted progressive ratio has not worked well in practice, and the contact rule is the one the lab's earlier experiments and analyses rest on.

## Consequences

- A ratio Paradigm without a `Counter` line needs firmware 4.0.1. On a 4.0.0 board PyMCU refuses it at the Compatibility Check and when the Interval comes. The message names the default and says that `Counter: Events` runs on 4.0.0.
- **Programs written for Events before 4.0.1 change meaning.** Their Requirement numbers are now read as milliseconds.
  - A number that isn't a multiple of 10, such as `Step: 5`, is refused at load, with a message saying to add `Counter: Events`.
  - A number that is, such as `Step: 10` or `Cap: 200`, loads as milliseconds of contact. That gives a Paradigm that lights almost at once, with no error.
  - So ProgramFormat.md warns in bold, and every shipped Program that counts Events (OptoTest5, OptoTest6 and two Paradigms of ParadigmExamples) says `Counter: Events`.
  - Training10_BreakPt now counts contact. It reproduces the 3.5.2 breakpoint program: Acclimation 10, then 1 s more contact for each Activation.
- With `Contact`, the Exponential series' `Scale` has no default. Its default of 5 is the Richardson–Roberts series in Events, and as milliseconds it would make every Requirement 10 ms.
- `Program.txt` now writes `Counter Contact` or `Counter Events` on every ratio Paradigm's line. A line without one was written before 4.0.1 and counted Events, so readers such as pyflic take a missing Counter as Events, not as the new default.
- The instruction protocol is unchanged. Flag bit 1 still asks for Contact, so a 4.0.0 board, which ignores it, can still be given Event Paradigms. The default lives in PyMCU, not in the firmware.
- ADR 0001's caution still applies: the contact count depends on the 270 ms smoothing and the Threshold, and a Well whose signal drifts above its Threshold keeps earning Activations with no fly. `Baseline: Adaptive` (ADR 0004) and pyflic's light QC are the checks on that.
