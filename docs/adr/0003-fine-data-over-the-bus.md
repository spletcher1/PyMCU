# Fine data comes over the bus from one DFM per bus, as a bigger Status record

From firmware 4.1.0, PyMCU can put one DFM per bus into fine mode for a recording. That DFM's Status record becomes a 2,304-byte block carrying the record, every ADC scan and every change in its per-Well decisions for the 200 ms. Blocks use the same ring, index, ACK and resend scheme as records, with a CRC-16. PyMCU polls the fine DFM every 200 ms and stores the blocks verbatim in a fine file next to the data file. The specification is [../v4-fine-mode-plan.md](../v4-fine-mode-plan.md).

The need: Events and Activations are decided every millisecond on a sum that changes with every scan, but the data file sees a snapshot every 200 ms, so the DFM's view of a feeding bout can't be recovered from the file and a Paradigm can't be re-run offline with different settings.

## Consequences

- Only one DFM per bus gets fine data, and the bus then has room for about five others at normal service. PyMCU refuses a Program with two fine DFMs.
- In fine mode that DFM holds 8.4 s of data instead of 2.6 min. The MCU is dedicated to it at 5 polls a second, so a longer outage is already a failure, and it is flagged by the existing overflow bit.
- The fine file grows about 1 GB a day. PyMCU refuses to start if the disk can't hold the Program's duration.
- The DFM remains the sole authority on Events. The raw scans let `LEDControl.c` re-run any Paradigm on a PC, which the firmware tests already do, but no threshold is ever re-decided on the MCU.
- No hardware changes, no new DFM RAM, and no new comm mechanism: the 3.5.0 reliability work carries over.

## Considered options

- **Transition fields in every record, for every DFM.** Contact ms, Event count and first-Event offset per Well, 30 bytes more per record. Cheap, but it reports the DFM's conclusions only, never the signal, so nothing can be re-run offline. Kept in reserve: it needs no mode and would suit a lab that wants onsets to the ms on every DFM.
- **A microSD card on the DFM's PMOD header.** The header is wired to hardware SPI2, so it is feasible, but it puts an SD command layer, a filesystem, a second DMA peripheral and card stalls on the firmware's critical path, and RD4 and RD6–RD9 on that header are also driven by the opto port's 1 ms write. Rejected for the amount of new code on an instrument whose last two releases were about reliability.
- **A daughter board on the PMOD header** receiving a UART3 stream and storing or forwarding it. Architecturally the cleanest, since the PIC only fires frames, but it is a hardware project: a board per DFM, power from the header, a Wi-Fi or card workflow. Rejected for now; the bus design above needs none of that.
- **A faster bus.** Would double the budget, but it is bus-wide: every DFM's firmware, the Pi's UART, the cable and the transceiver. Left as a separate change if ever needed.
- **Per-ms sums instead of scans.** 24 kB/s, which the bus can't carry. Scans plus the tick that consumed each one carry the same information at 7 kB/s.
