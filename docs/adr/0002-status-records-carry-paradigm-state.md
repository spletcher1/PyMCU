# Status records carry full per-Well Paradigm state; the DFM buffers about 2.6 minutes

From firmware 4.0.0, every Status record carries each Well's Phase, total Activations, Requirement, Progress and LED on-time, plus the instruction number. Records grow from 56 to 127 bytes. The DFM has 128 KB of RAM, so its buffer drops from 1,500 records (5 minutes) to 780 (about 2.6 minutes of outage), and a reply carries at most 27 records instead of 60. 28 were planned, but a 28-record reply is about 3,560 bytes on the wire, which overruns the 3,482-byte receive buffer of every DFM before 4.0.0 sharing the bus; 27 records (at most 3,444 bytes) fit. Running totals are sent in full rather than as per-record changes, so a lost or resent record can't corrupt them.

## Considered Options

- **Send per-record changes and let PyMCU keep the totals.** Records would be smaller and the buffer longer, but any lost record makes every later total wrong.
- **Leave out Requirement and let PyMCU work it out from the Type settings.** That gives about 103 bytes and about 3.2 minutes, but Requirement then depends on PyMCU's arithmetic matching the firmware's.
- **Keep 56-byte records.** The Paradigm state would be impossible to report.

To make room, well signals are 2-byte averages instead of 3-byte sums, because PyMCU already discards the extra precision. The per-record copies of frequency, pulse width and dark are replaced by the instruction number.
