# Fine mode: per-scan and per-ms data from one DFM over the bus

Firmware 4.1.0 and the matching PyMCU. Decided in the October 2026 design review; implementation not started in either repo (checked 2026-10-18). Terms are in [../CONTEXT.md](../CONTEXT.md). Why this design and not an SD card, a daughter board or extra record fields: [adr/0003](adr/0003-fine-data-over-the-bus.md). It builds on firmware 4.0.0, whose instruction and Status record layouts are in the DFMV3_V2 `README.md` and whose Paradigm rules are in [ProgramFormat.md](ProgramFormat.md), and starts only after 4.0.0 has passed its bench checks.

This document is the whole specification. An implementer needs nothing else beyond the two repos.

- [Goal](#goal)
- [Terms](#terms)
- [Contract](#contract)
- [Delivery stages](#delivery-stages)
- [Firmware reference](#firmware-reference)
- [Block layout](#block-layout)
- [PyMCU reference](#pymcu-reference)
- [Converter](#converter)
- [Tests](#tests)
- [Bench checks](#bench-checks)
- [Numbers](#numbers)

## Goal

The data file holds one Status record per 200 ms: a 128-scan average per Well and the Paradigm state at that moment. The DFM decides every millisecond on a 128-scan sum that changes with every ADC scan (about 470 a second), so Event and Activation edges can't be recovered from the file to better than 200 ms, and a Paradigm can't be re-run offline with a different Threshold or Event gap.

Fine mode makes one DFM per bus report, for every 200 ms period, every ADC scan and every change in its per-Well decisions, inside the Status record's existing reliability scheme. PyMCU stores the blocks verbatim in a fine file next to the data file, and a converter turns them into tables that join to the data file on the record index. The DFM stays the sole authority on Events; the raw scans let the same `LEDControl.c` that the firmware tests use re-run any Paradigm on a PC.

## Terms

These are in [../CONTEXT.md](../CONTEXT.md) under Data; the glossary is the source of truth for them.

- **Scan**: one pass of the ADC over all 13 inputs, about every 2.1 ms. Each scan gives one 10-bit reading per Well.
- **Tick**: one 1 ms pass of the DFM's LED logic. Ticks are numbered 0 to 199 within a Status record's 200 ms. Not "Step": that is a progressive ratio setting, and in the firmware `Step...` functions mean "advance".
- **Decision word**: the DFM's three per-Well bits after a Tick: contact (signal above Threshold), lit (the Well's own Paradigm output, before Linkage) and Event in progress.
- **Fine block**: what a Status record becomes in fine mode: the 127-byte record plus that period's scans and decision changes, 2,304 bytes.
- **Fine mode**: a DFM state, set by PyMCU for one recording, in which the DFM buffers and sends fine blocks instead of Status records.

## Contract

What the two sides promise each other. The reference sections say how.

1. **One fine DFM per bus.** PyMCU refuses a Program with two. The others get normal service.
2. **The mode is bounded by the recording.** PyMCU sends the fine-mode request, then the buffer reset that starts recording. The reset applies the mode. Every buffer reset clears it unless a request preceded that reset, and PyMCU sends a plain reset when recording stops.
3. **A block replaces a record.** In fine mode the DFM stores one 2,304-byte block per 200 ms in the same ring, with the same index, ACK, partial ACK and resend behaviour. A status request returns one block. A latest-status request returns the record embedded in the newest block. The empty reply is unchanged.
4. **Every block holds exactly 200 Ticks,** because the record boundary is now the 200th Tick, in both modes.
5. **A block is self-contained.** It carries the exact running sums and the decision word at its start, so a lost block costs its own 200 ms and nothing after it.
6. **Blocks are checked by CRC-16,** records by their existing checksum.
7. **PyMCU polls the fine DFM every 200 ms,** and again at once while the block says more are queued.
8. **The fine file holds blocks verbatim.** The data file is unchanged in form, including for the fine DFM.
9. **Firmware before 4.1.0 ignores the mode request** (unknown command, error bit 0x04). PyMCU never sends it to such firmware.

## Delivery stages

Each stage ends when its criterion holds. Bench ticks need real DFMs; everything else runs on a PC.

**S1 – Firmware block encoder.** New hardware-free module `src/FineBlock.c` and `src/FineBlock.h` ([Firmware reference](#fineblockc)), plus `tests/test_fineblock.c` built by `tests/run_tests.py`. Done when: every test in [Tests, firmware](#firmware) passes, and the golden block hex is pinned in the C test.

**S2 – Firmware integration.** The Tick-counted record boundary, the mode request, the dual-size ring, fine-mode replies, the `LEDControl.c` getters, version string `4.1.0`, README updates ([Firmware reference](#firmware-reference)). Done when: `run_tests.py` passes, the build fits with the stack reserve no smaller than 4.0.0's, and on a DFM with a test signal (a) a status request after the mode request and a reset returns a 2,304-byte block every 200 ms whose CRC and embedded record check, (b) a plain reset returns it to 127-byte records, (c) `TEST_PIN` shows the block store under 0.5 ms, and (d) error bit 0x80 never sets during an hour in fine mode.

**S3 – PyMCU protocol.** `COMM`, `StatusPacket`, `DataGetter` changes ([PyMCU reference](#pymcu-reference)), with `tests/test_protocol.py` decoding the same golden block the firmware test pins. Done when: `python -m unittest discover -s tests` passes and the Python decoder's CRC check and field values agree with the C test's inputs.

**S4 – PyMCU recording.** The Program key, refusals, mode-before-reset ordering, the fine file, the stop reset, the disk check, the Status panel row. Done when: the tests in [Tests, PyMCU](#pymcu) pass, and a recording with a fine DFM on the bench produces a fine file whose record indices are continuous and a data file identical in form to a normal DFM's.

**S5 – Converter.** `tools/fine_to_csv.py` ([Converter](#converter)). Done when: its tests pass and it converts a bench fine file with zero CRC failures and reports any index gaps.

**S6 – Bench.** [Bench checks](#bench-checks), all passed, with the results noted at the top of this document.

## Firmware reference

### Version

`VersionToUART2()` in `src/UART2.c` sends `4.1.0`.

### Record boundary from Ticks

The 200 ms record tick no longer comes from TMR1. `main()` counts Ticks:

```c
if (timerFlag_1ms) {
    SetOptoState(StepLEDControl(CurrentValues));
    FineTick(tickInRecord);          // fine mode only, see below
    StepUART();
    timerFlag_1ms = 0;
    if (++tickInRecord >= 200) {
        StepPacketManager();         // stores the record or block
        tickInRecord = 0;
    }
}
if (analogUpdateFlag) {
    StepADC();
    FineScan(tickInRecord);          // fine mode only
    analogUpdateFlag = 0;
}
```

This order matters: a scan folded in during an iteration is first seen by the Tick that runs in the next iteration, and a block's store happens before any scan that belongs to the next block. `tickInRecord` is reset to 0 by the buffer reset as well, so the first record after a reset also spans 200 Ticks.

TMR1 keeps its 200 ms period for the heartbeat toggle and `timerFlag_1sec`. `timerFlag_200ms` and its branch in `main()` go. The README's timer table and the "Status record" row change accordingly.

### Fine-mode request, command 0xF5

A 4-byte request like the others, read raw: `[ID, 0xF5, mode]` where mode is `0x01` normal or `0x02` fine. Both values are non-zero so the raw read works without COBS decoding. The DFM checks `packetSize == 4`, replies ACK and stores the mode as *pending*. Any other mode byte is NACKed. A wrong length sets 0x20 as for the other 4-byte requests.

The pending mode becomes the *active* mode inside the buffer reset (`InitializeStatusPacketBuffer()`), and the pending mode is then set back to normal. So a reset with no preceding request always leaves the DFM in normal mode. The mode request is not an ACK, so `isStatusSetAwaitingAck` clears as for other requests.

`PacketManager` gains `SetPendingMode(uint8_t mode)`, `GetActiveMode(void)`, `GetRecordSize(void)` (127 or 2304) and `GetMaxPacketsPerReply(void)` (27, the `MAXPACKETS` of `src/UART2.c`, or 1).

### The ring in both modes

`struct StatusPacket statusBuffer[RINGBUFFERSIZE]` becomes `unsigned char ringBytes[RING_BYTES]` with `RING_BYTES = 99072`, which is 43 × 2,304 and holds 780 × 127 = 99,060 with 12 bytes over. Slot `i` starts at `ringBytes + i * GetRecordSize()`.

| Mode | Record size | Ring capacity | Records per reply | Outage held |
|---|---|---|---|---|
| Normal | 127 | 780 | 27 | 2.6 min |
| Fine | 2,304 | 42 | 1 | 8.4 s |

In fine mode slot 42 (bytes 96,768 to 99,071) is the *staging* block, where the block in progress is built. A block is copied from staging into the ring slot at `head` when it is stored, so a resend can never send a half-built block. In normal mode `AddCurrentStatus()` keeps writing the record straight into the slot at `head`, as today.

`head`, `tail`, `tailPlaceHolder`, `bufferSize`, `UnackedCount()`, `ResetTail()`, `SetTailPlaceHolder()`, `AckStatusPacketsThrough()` and the overflow rule are unchanged apart from indexing by `GetRecordSize()` and reading the record index from the right offset: byte 119 of a record, byte 2 of a block (see [Block layout](#block-layout); the embedded record's own index at block offset 135 is the same number). The 0x02 overflow flag keeps its meaning: in fine mode it is raised when the 43rd block overwrites the oldest.

`lastPacket` becomes a byte pointer. `GetLastestStatus()` returns the embedded record (block + 16) in fine mode.

### Replies

In `src/UART2.c`:

- `CurrentStatusPacketSetToUART2()` copies `GetMaxPacketsPerReply()` records of `GetRecordSize()` bytes. In fine mode that is one block. `COBSBUFFERSIZE` (3,693 with 27 records per reply) already holds a 2,304-byte block plus COBS overhead (2,315 bytes).
- `LatestStatusPacketToUART2()` sends the 127 bytes that `GetLastestStatus()` points at, in both modes.
- `EmptyPacketToUART2()` is unchanged: the 127-byte empty record is the empty reply in both modes. PyMCU tells the two apart by length.
- The partial ACK works on blocks unchanged, because it is index-based. With one block per reply it only ever acknowledges that block.

The byte 1 filter in `UARTRxDmaChannelHandler()` is why a block's first byte is the DFM ID: every other DFM on the bus receives the block and must see an ID that isn't its own.

### LEDControl.c

`WellState` gains `uint8_t contact` and `uint8_t lit`, set on every path through `StepWell()`, including the early returns for Wells set On or Off (contact 0; lit 0 for Off, 1 for On). `wasLit` keeps its current behaviour, including not changing for On/Off Wells, so no Paradigm test changes.

Three getters return 12-bit masks (bit 0 = Well 1) reflecting the last Tick:

- `uint16_t GetContactBits(void)` from `contact`.
- `uint16_t GetOwnLitBits(void)` from `lit`.
- `uint16_t GetBoutBits(void)` from `inBout`, reported as 0 for Wells that don't run the Paradigm (same rule as `GetPhaseBits()`).

### AnalogInputs.c

`StepADC()` copies the thirteen raw readings it folds in to `int LastScan[13]`, Well order, so the block encoder reads the same values the sums received.

### FineBlock.c

Hardware-free, like `LEDControl.c`, so it compiles in `tests/run_tests.py`. It depends on nothing but `<stdint.h>`, `<string.h>` and `PacketManager.h` for `STATUSPACKETSIZE`.

```c
#define FINE_BLOCK_SIZE 2304
#define FINE_FORMAT_VERSION 1
#define FINE_SCAN_SLOTS 100
#define FINE_CHANGE_SLOTS 86

typedef struct {
    uint8_t *block;
    uint8_t scans, changes, overflow, ticks;
    uint64_t lastWord;
} FineBlockBuilder;

// Zeroes the block and writes the ID, format version, the twelve running sums and the
// decision word in force at the start.
void FineBlockBegin(FineBlockBuilder *b, uint8_t *block, uint8_t dfmID, const int *sums, uint64_t startWord);
// Appends a scan (12 raw readings, 0-1023) first seen by Tick tick. Counts an overflow if
// the slots are full.
void FineBlockAddScan(FineBlockBuilder *b, const int *values, uint8_t tick);
// Records the decision word after Tick tick if it differs from the previous word. Counts
// an overflow if the slots are full. Always counts the Tick.
void FineBlockAddTick(FineBlockBuilder *b, uint8_t tick, uint64_t word);
// Writes the record index and counts, copies the 127-byte record in, and computes the CRC.
void FineBlockFinish(FineBlockBuilder *b, uint32_t recordIndex, const uint8_t *record);
// Patches the "blocks queued" field, which lies outside the CRC.
void FineBlockSetQueued(uint8_t *block, uint16_t queued);
uint64_t FineDecisionWord(uint16_t contact, uint16_t lit, uint16_t bout);
uint16_t Crc16(const uint8_t *data, uint32_t length);
```

`Crc16` is CRC-16/CCITT-FALSE: polynomial 0x1021, initial value 0xFFFF, no reflection, no final XOR; `Crc16("123456789", 9)` is 0x29B1. It is table-driven (a 512-byte `const` table in flash) so that finishing a block costs about 0.15 ms. A bit-at-a-time loop would cost over 1 ms and trip error bit 0x80.

### Capture in main.c and PacketManager.c

A `static FineBlockBuilder builder` lives with the main loop (or in `PacketManager.c`; either, but one place).

- `FineTick(tick)`: in fine mode, `FineBlockAddTick(&builder, tick, FineDecisionWord(GetContactBits(), GetOwnLitBits(), GetBoutBits()))`.
- `FineScan(tick)`: in fine mode, `FineBlockAddScan(&builder, LastScan, tick)`.
- `StepPacketManager()` in fine mode: build the record into the staging block at offset 16 with the same code `AddCurrentStatus()` uses (`FillCurrentStatus`, `FillParadigmStatus`, error byte, index, checksum), then `FineBlockFinish(&builder, recordCounter, staging + 16)`, copy the 2,304 bytes to the slot at `head`, advance `head`, `recordCounter` and the overflow bookkeeping exactly as `AddCurrentStatus()` does, then `FineBlockBegin(&builder, staging, dfmID, CurrentValues, builder.lastWord)` for the next block. `CurrentValues[0..11]` are the exact sums at that moment.
- The buffer reset, in fine mode, calls `FineBlockBegin(&builder, staging, dfmID, CurrentValues, 0)` after resetting the ring, so the first block's start word is zero.
- `CurrentStatusPacketSetToUART2()` calls `FineBlockSetQueued(block, bufferSize)` on the block it is about to send, after taking it from the ring, so the value is the number of blocks still unsent behind it.

Timing budget: the whole store (record fill, finish with CRC, copy) must stay under 0.5 ms. Measure with `TEST_PIN` (RA2) around `StepPacketManager()` on the bench.

### README

Add to `README.md` in DFMV3_V2: a "Changes in 4.1.0" section (the Tick-counted boundary, the 0xF5 request, fine mode, the ring sizes), the 0xF5 row in the command table, a "Fine block" subsection that links here for the layout, and the timer table change. Keep the 4.0.0 "Status record" table as it is.

## Block layout

2,304 bytes. Multi-byte fields are big-endian. The embedded record keeps its own layout and checksum.

| Offset | Bytes | Field |
|---|---|---|
| 0 | 1 | DFM ID. First, because every DFM on the bus filters frames on this byte. |
| 1 | 1 | Format version: 1 |
| 2 | 4 | Record index, the same number as in the embedded record |
| 6 | 1 | Ticks in block: 200 |
| 7 | 1 | Scan count, 0 to 100 |
| 8 | 1 | Change count, 0 to 86 |
| 9 | 1 | Overflow count: scans or changes that did not fit, saturating at 255 |
| 10 | 6 | Reserved, zero |
| 16 | 127 | Status record, `struct StatusPacket`, as it would have been sent in normal mode |
| 143 | 36 | Running sums at block start: 12 × 3 bytes, Wells 1 to 12. Each is the exact 128-scan sum, 0 to 130,944. |
| 179 | 5 | Decision word at block start |
| 184 | 1,600 | 100 scan slots × 16 bytes |
| 1,784 | 516 | 86 change slots × 6 bytes |
| 2,300 | 2 | Blocks queued behind this one when it was sent. Outside the CRC; a corrupt value only mis-paces polling. |
| 2,302 | 2 | CRC-16 over bytes 0 to 2,299 |

**Scan slot, 16 bytes.** Bytes 0 to 14 hold the twelve 10-bit readings, Well 1 first, packed most-significant bit first: treat the 15 bytes as a 120-bit big-endian integer in which Well n occupies bits 120 − 10n + 9 down to 120 − 10n. Byte 15 is the Tick that first saw the scan, 0 to 199. Unused slots are zero.

Packing, as reference code:

```c
memset(out, 0, 15);
bit = 0;
for (w = 0; w < 12; w++)
    for (i = 9; i >= 0; i--, bit++)
        if ((values[w] >> i) & 1)
            out[bit >> 3] |= 0x80 >> (bit & 7);
```

**Decision word, 5 bytes.** A 40-bit big-endian integer: bits 39 to 36 zero, bits 35 to 24 contact, bits 23 to 12 lit, bits 11 to 0 Event in progress. Within each 12-bit field, bit 0 is Well 1. So `word = (contact << 24) | (lit << 12) | bout`.

**Change slot, 6 bytes.** Byte 0 is the Tick, 0 to 199. Bytes 1 to 5 are the decision word after that Tick. A slot is written only when the word differs from the word after the previous Tick; for Tick 0 the comparison is with the block's start word.

**Reconstruction rule** (what the converter and any offline re-run rely on): the sums seen by Tick m are the start sums plus every scan whose slot byte 15 is ≤ m, each scan adding its reading and removing the reading 128 scans earlier. The decision word before Tick 0 is the start word, and after Tick k it is the last change slot with Tick ≤ k, or the start word if there is none.

## PyMCU reference

### Program file

A new key in `[DFM]` sections: `FineData: Yes` or `No`, default No. Add `"finedata"` to `_DFM_KEYS` in `Program.py`, not to `_ENVMON_KEYS`, and `fineData = False` to `InstructionSet.__init__`. After the device sections load, `_Load()` raises `ProgramError("Only one DFM can have FineData: Yes")` naming both IDs if two sets have it. `GetProgramDescription()` mentions "fine data" for that DFM.

### Refusals before a Program starts

In `DFMGroup.CheckProgramCompatibility()`:

- A fine DFM whose firmware fails `COMM.UsesFineFirmware()`: `"DFM {id} (firmware {v}) can't record fine data. That needs DFM firmware 4.1.0 or later."`
- Free space on the data directory's filesystem below `needed = 1.1 × FINE_BYTES_PER_SECOND × duration_seconds + 2 GB`, where `FINE_BYTES_PER_SECOND = 5 × 2304`: `"Fine data for DFM {id} needs about {needed} GB; {free} GB free."` Move `GetFreeMegaBytes()` out of `MainViewModel` into a helper both can call, measuring the directory the data files go in.

### COMM.py

```python
FINE_MODE_REQUEST = 0xF5
FINE_FIRMWARE = (4, 1, 0)
FINE_BLOCK_SIZE = 2304
FINE_FORMAT_VERSION = 1

def UsesFineFirmware(version): ...   # FirmwareVersionTuple(version) >= FINE_FIRMWARE
def Crc16(data): ...                 # CRC-16/CCITT-FALSE, same parameters as the firmware

class UARTCOMM:
    def SendFineMode(self, ID, fine):
        """Returns True if the DFM ACKed. The mode takes effect at the next buffer reset."""
        self._Send((ID, FINE_MODE_REQUEST, 2 if fine else 1))
        return self._ReadAck(ID)
```

`STATUS_FRAME_SIZE` (5,000) and `STATUS_TIMEOUT` already cover a block reply. Update the module docstring.

### StatusPacket.py

- `ProcessStatusPacketPletcherV4()` takes a `base` offset instead of computing it from `packetNum`, so the embedded record can be parsed at block offset 16. Keep a wrapper with the old signature if that is less churn.
- New attributes, default `None` or 0: `isFine`, `fineBlock` (the 2,304 bytes), `fineScanCount`, `fineChangeCount`, `fineOverflow`, `fineQueued`.
- New method `ProcessFineBlock(bytesData, startTime)`: checks length 2,304, byte 0 equals the DFM ID, byte 1 equals the format version, and `Crc16(bytes 0..2299) == bytes 2302..2303`. On failure `processResult = CHECKSUMERROR` (so no ACK and the DFM resends). On success parses the header fields, the embedded record via the V4 parser at base 16 (whose own checksum is also checked), sets `recordIndex` from the header, `isFine = True`, and keeps the raw bytes.
- `GetDataBufferPrintPacket()` is unchanged: a fine DFM's data-file rows come from the embedded record.

### DataGetter.py

Reader-process state: `finePending` (IDs whose fine-mode request was ACKed, waiting for the reset) and `fineDFMIDs` (IDs now in fine mode). Both are cleared by `FindDFMInternal()`.

- New `COMMANDTYPE.FINE_MODE` with `SendFineMode(ID, fine)` on the outside (a `_Request` with a 3 s timeout, like the instruction sends). On ACK, the reader adds or discards the ID in `finePending`.
- `BufferResetInternal()`: on a successful reset, the ID moves from `finePending` to `fineDFMIDs` if it was pending, otherwise it is discarded from `fineDFMIDs`. This mirrors the firmware exactly.
- `ProcessPacket()`: for a PLETCHERV3 DFM, a payload of exactly 2,304 bytes is one fine block (`ProcessFineBlock`); 127 bytes is a record or the empty record as today; anything else is `WRONGNUMBYTES`. Decide by length, never by `fineDFMIDs`, so a mismatch between the two sides still yields correct data.
- Polling in `ReadWorker()`: fine DFMs are left out of `ReadRound()` and read on their own timer every `FINE_POLL_INTERVAL = 0.2` s. After a block whose `fineQueued > 0`, that DFM is read again on the next loop pass, through the existing lagging mechanism. Commands still get their turn between reads.
- `_Acknowledge()` is unchanged: a block that failed its CRC is not ACKed.

### DFM.py and DFMGroup.py

- `DFM` gains `isFineModeNeeded`, `isFine` (set from the Program at recording start), `fineBlocks` (a `deque` of bytes, `maxlen` 600), `fineBlocksReceived` and `fineQueued`.
- `_AddPacket()`: when `sp.isFine`, append `sp.fineBlock` to `fineBlocks` during recording, increment `fineBlocksReceived`, set `fineQueued`. If `sp.fineOverflow > 0`, one WARNING per recording: `"({id}) Fine block overflow: {n} scans or changes dropped"`.
- `CheckStatusV3()`, order within one pass: version, fine mode, buffer reset, instruction, linkage. When `isFineModeNeeded` is set, send the mode first; if it is not ACKed, keep both `isFineModeNeeded` and `isBufferResetNeeded` set, set the retry time and return before the reset. The reset is never sent while the mode is still owed. After `COMMAND_RETRY_INTERVAL` × 3 failures, one ERROR: `"({id}) Fine mode not set; recording without fine data"`, clear `isFineModeNeeded`, and let the reset go.
- `DFMGroup.StartRecording()`: before setting `isBufferResetNeeded`, set `d.isFineModeNeeded = d.isFine = iset.fineData` for each DFM, and reset `fineBlocksReceived`.
- `DFMGroup.StopRecording()`: after `isWriting` clears, call `self.MP.SendBufferReset(d.ID)` synchronously for each fine DFM. If it fails, one NOTICE: `"({id}) Still in fine mode until its next buffer reset"`.
- Fine file: `_OpenDataFile()` also opens `DFM{id}_fine_{n}.bin` in the run directory for a fine DFM, with the same `n` as the data file, in `self.theFineFiles[id]`. `IncrementOutputFile()` rolls both. `_WriteBufferedData()` writes and flushes the queued blocks, removing them only after a successful write, with the same once-per-failure message pattern. `WriteEnder()` closes the fine files.
- `ReadWorker()` (the idle reader) needs no change: fine mode never runs outside recording.

### Status panel

`Mainwindow.ui`: one more row in the DFM page's Status panel, label "Fine", value `FineLabel`. `UpdateParadigmDisplay()` sets it to `"-"` unless `dfm.isFine`, otherwise `"{received} / {queued}"`. A tooltip explains: blocks received this recording / blocks waiting on the DFM.

## Converter

`tools/fine_to_csv.py FILE... [--parquet]`. Standard library only, except `--parquet`, which imports pandas and pyarrow and fails with a one-line message if they're missing.

For each input file, read 2,304-byte blocks and validate each as `ProcessFineBlock` does. Write three files next to the input, replacing `.bin`:

- `_blocks.csv`: `RecordIndex, Ticks, ScanCount, ChangeCount, Overflow, Sum1..Sum12, Contact1..Contact12, Lit1..Lit12, Bout1..Bout12` (the start sums and the start word's bits, 0/1).
- `_scans.csv`: `RecordIndex, Tick, W1..W12`, one row per scan slot used.
- `_changes.csv`: `RecordIndex, Tick, Contact1..Contact12, Lit1..Lit12, Bout1..Bout12`, one row per change slot used.

Rows join to the data file on `RecordIndex`, which is the data file's `Index` column. At the end print, per input: blocks read, CRC failures (skipped), index gaps (first and last index of each gap), and the output paths. Exit non-zero if any CRC failed.

## Tests

### Firmware

`tests/test_fineblock.c`, built by `tests/run_tests.py` together with `test_ledcontrol.c` (one executable each, both run).

1. `Crc16("123456789")` is 0x29B1; `Crc16` of an empty buffer is 0xFFFF.
2. Packing: values `{1023, 0, 512, 1, 2, 3, 4, 5, 6, 7, 8, 9}` pack to the 15 bytes computed by hand in the test, and unpack back.
3. `FineDecisionWord(0x001, 0x800, 0xFFF)` is `0x001800FFF`.
4. A block begun with known sums and start word, 3 scans at Ticks 0, 2, 4 and 200 Ticks in which the word changes at Ticks 1 and 150, finished with record index 7 and a known 127-byte record, equals the pinned golden hex (`GOLDEN_FINE_BLOCK`, 4,608 hex characters, generated once by this encoder and validated independently by the Python test). The golden record is the same 127 bytes as `Record()` in PyMCU's `tests/test_protocol.py` with its defaults, so both repos pin the same block.
5. The same word at every Tick writes no change slots; change count 0.
6. 87 changes: 86 slots filled, overflow count 1. 101 scans: 100 slots filled, overflow count incremented.
7. `FineBlockSetQueued` changes bytes 2,300 to 2,301 and the CRC still verifies.

### PyMCU

Add to `tests/test_protocol.py`:

1. `Crc16` check value and the golden block's CRC.
2. `ProcessFineBlock` on the golden block: every header field, the three scans' values and Ticks, the two changes, the start sums and word, and the embedded record's fields as the existing V4 record test checks them.
3. A flipped byte inside the CRC range gives `CHECKSUMERROR`; a flipped byte at offset 2,300 does not.
4. `DataGetter.ProcessPacket` routes a 2,304-byte payload to a fine packet and a 127-byte one to a record, for a PLETCHERV3 DFM.
5. The reader's mode mirror: a mode ACK then a reset puts the ID in `fineDFMIDs`; a reset alone removes it.
6. A block with `fineQueued > 0` marks the DFM lagging; with 0 it doesn't.

Add to `tests/test_program.py`: `FineData: Yes` loads and sets `fineData`; two fine DFMs raise the error naming both; `FineData` in `[ENVMON]` is an unknown-key error.

Add to `tests/test_dfm.py`: at recording start the mode is sent before the reset and the reset is withheld while the mode is NACKed; after the retry limit the reset goes and the ERROR is recorded; fine blocks are written to the fine file and removed only after a successful write; the stop sends a reset to the fine DFM; the compatibility check refuses firmware 4.0.0 and insufficient free space (with the free-space helper patched).

Add `tests/test_fine_to_csv.py`: the golden block, written as a one-block file, converts to the three CSVs with the expected rows; a file with a corrupt block exits non-zero and reports one CRC failure; two blocks with indices 7 and 9 report one gap.

## Bench checks

On one bus: one fine DFM and five others, a test signal on at least two Wells of the fine DFM, a Program with `FineData: Yes` on the fine DFM, 30 minutes.

1. The five normal DFMs log no "Lost … records" messages.
2. The fine file converts with zero CRC failures and zero index gaps; its `_scans.csv` has about 94 rows per record index.
3. For a Well with the test signal, the changes table shows contact rising and falling at the Ticks where the scans cross the Threshold, and the data file's `OnMs` for that record equals the lit time the changes imply.
4. Disconnect the bus for 5 s: the fine DFM's next blocks arrive with no gap. Disconnect for 15 s: a gap is reported, error 0x02 appears once in the data file, and the first block after the gap has the overflow accounted for in its index.
5. The Status panel's Fine row counts up and shows queued 0 in steady state.
6. Stop the recording: a status request to the fine DFM afterwards returns 127-byte records.
7. `TEST_PIN` around the block store stays under 0.5 ms, and error 0x80 never appears in the fine DFM's data file.

## Numbers

| Figure | Value |
|---|---|
| Bus rate | 250 kbaud, 25 kB/s |
| Block on the wire with COBS | 2,315 bytes, about 93 ms |
| Fixed overhead per request-reply, including the ACK | about 26 ms |
| Bus share of one fine DFM at 5 polls/s | about 59% |
| Other DFMs that fit at the 4 s poll | about 5 |
| Fine ring | 42 blocks, 8.4 s |
| Fine file growth | 11,520 bytes/s, about 1 GB/day |
| DFM RAM added | 12 bytes for the ring, under 100 bytes elsewhere |
| Block store CPU cost | about 0.2 ms with the table-driven CRC |
