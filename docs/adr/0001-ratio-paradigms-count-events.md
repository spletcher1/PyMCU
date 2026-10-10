# Ratio Paradigms count Events, not contact time

Through DFM firmware 3.5.0, progressive ratio counted "licks". These were really milliseconds of Contact time, sampled every 1 ms against a signal smoothed over about 270 ms, so one feeding bout counted hundreds of times. From firmware 4.0.0, progressive ratio, fixed ratio and Acclimation count Events (feeding bouts, separated by the Event gap) instead. "10 more bouts" is the unit experimenters mean, and it doesn't depend on the smoothing window.

## Consequences

Old Programs that use progressive ratio, or acclimation encoded in the high bits of OptoFrequency, are refused at load time with instructions for rewriting them. Converting them would silently turn something like "1000 ms of contact" into "1000 feeding bouts". Other old Paradigms (open-loop, closed-loop, fixed interval, non-feeding) still load and convert exactly.
