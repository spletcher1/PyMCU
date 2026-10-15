"""The DFM protocol: the instruction frame for each firmware generation, version strings and
56-byte Status record parsing. Shared with DFMV3_V2 (src/UART2.c, src/PacketManager.h): both
sides must agree on these bytes."""
import support  # noqa: F401  (must come first)

import datetime
import struct
import unittest

import COMM
import Enums
import Instruction
import StatusPacket
from StatusPacket import Checksum32

# The same closed-loop instruction as firmware 1.0.5 (2-byte times, 41 bytes) and 2.0.0 and later
# (4-byte times, 47 bytes) receive it: ID 5, dark on, 40 Hz, 8 ms, decay 1000, delay 0, max time
# on 2000, thresholds 20, always on, off, 30, then eight at 1023. Derived with struct, so a change
# to the payload code fails here.
GOLDEN_1_0_5 = "05fd010028000803e8000007d000140000ffff001e03ff03ff03ff03ff03ff03ff03ff03fffffff2cb"
GOLDEN_2_0_0 = "05fd0100280008000003e800000000000007d000140000ffff001e03ff03ff03ff03ff03ff03ff03ff03fffffff2cb"


def ClosedLoop():
    instruct = Instruction.DFMInstruction(Enums.DARKSTATE.ON, 40, 8, 1000, 0, 2000)
    instruct.SetOptoValues([20, 0, -1, 30] + [1023] * 8)   # 0 is always on, -1 is off
    return instruct


def Frame(instruct, timingSize, dfmID=5):
    packet = bytes([dfmID, COMM.INSTRUCTION_REQUEST]) + COMM.InstructionPayload(instruct, timingSize)
    return packet + Checksum32(packet).to_bytes(4, "big")


def Record(dfmID=5, index=7, errorFlags=0, wells=None, training=(), frequency=40, pulseWidth=8, dark=1):
    """A 56-byte Status record as firmware 1.0.5 to 3.5.0 sends it (PacketManager.h): each Well a
    3-byte sum of 128 scans, which PyMCU shifts right by 7. From 2.0.0 the top bit of a Well is set
    while it is in training; PyMCU keeps that as +65536 in the data file."""
    wells = wells or [100 + w for w in range(12)]
    body = bytes([dfmID, errorFlags])
    for w, value in enumerate(wells):
        body += ((value << 7) | (0x800000 if w in training else 0)).to_bytes(3, "big")
    body += (512 << 7).to_bytes(3, "big")   # supply voltage reading
    body += struct.pack(">HHHB", 0x0003, frequency, pulseWidth, dark)
    body += struct.pack(">I", index)
    return body + Checksum32(body).to_bytes(4, "big")


class Instructions(unittest.TestCase):
    def test_golden_frames(self):
        self.assertEqual(Frame(ClosedLoop(), 2).hex(), GOLDEN_1_0_5)
        self.assertEqual(Frame(ClosedLoop(), 4).hex(), GOLDEN_2_0_0)
        self.assertEqual((len(bytes.fromhex(GOLDEN_1_0_5)), len(bytes.fromhex(GOLDEN_2_0_0))), (41, 47))

    def test_fields(self):
        payload = COMM.InstructionPayload(ClosedLoop(), 4)
        dark, frequency, pulseWidth, decay, delay, maxTimeOn = struct.unpack(">BHHIII", payload[:17])
        self.assertEqual((dark, frequency, pulseWidth, decay, delay, maxTimeOn), (1, 40, 8, 1000, 0, 2000))
        self.assertEqual(struct.unpack(">12H", payload[17:]), (20, 0, 0xFFFF, 30) + (1023,) * 8)

    def test_baseline_moves_thresholds_not_on_off(self):
        instruct = ClosedLoop()
        instruct.SetBaseline([100] * 12)
        self.assertEqual(list(instruct.adjustedThresholds[:4]), [120, 0, -1, 130])

    def test_firmware_needed(self):
        self.assertIsNone(ClosedLoop().FirmwareNeeded())
        fixedInterval = Instruction.DFMInstruction(Enums.DARKSTATE.OFF, 40, 8, 1000, 5000, 0)
        self.assertIsNone(fixedInterval.FirmwareNeeded())
        for settings, words in (((40, 32776, 1000, 500, 0), "non-feeding"), ((1576, 8, 1000, 0, 0), "training"),
                                ((40, 8, 1000, 5000, 20000), "progressive ratio"), ((40, 8, 70000, 0, 0), "65535")):
            reason = Instruction.DFMInstruction(Enums.DARKSTATE.OFF, *settings).FirmwareNeeded()
            self.assertIn(words, reason)
            self.assertIn("2.0.0", reason)


class Versions(unittest.TestCase):
    def test_version_tuples(self):
        self.assertEqual(COMM.FirmwareVersionTuple(b"2.0.1"), (2, 0, 1))
        self.assertEqual(COMM.FirmwareVersionTuple("3.5.0"), (3, 5, 0))
        self.assertEqual(COMM.FirmwareVersionTuple(b"junk"), ())
        self.assertEqual(COMM.FirmwareVersionTuple(None), ())

    def test_what_each_firmware_takes(self):
        self.assertFalse(COMM.SupportsPartialAck(COMM.LEGACY_VERSION))
        self.assertFalse(COMM.SupportsPartialAck(b"2.0.1"))
        self.assertTrue(COMM.SupportsPartialAck(b"3.5.0"))
        self.assertFalse(COMM.UsesParadigmFirmware(b"3.5.0"))
        self.assertTrue(COMM.UsesParadigmFirmware("4.0.0"))
        self.assertFalse(COMM.UsesParadigmFirmware(b""))


class Records(unittest.TestCase):
    def Parse(self, data):
        sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
        sp.ProcessStatusPacket(data, datetime.datetime(2026, 1, 1), 0)
        return sp

    def test_record(self):
        sp = self.Parse(Record(index=7, errorFlags=0x01, training=(0,)))
        self.assertEqual(sp.processResult, Enums.PROCESSEDPACKETRESULT.OKAY)
        self.assertEqual((sp.recordIndex, sp.errorFlags, sp.darkStatus, sp.optoFrequency, sp.optoPulseWidth), (7, 1, 1, 40, 8))
        self.assertEqual(list(sp.analogValues), [100 + 65536] + [100 + w for w in range(1, 12)])
        self.assertEqual(sp.packetTime, datetime.datetime(2026, 1, 1, 0, 0, 1, 400000))

    def test_bad_checksum(self):
        data = bytearray(Record())
        data[5] ^= 0xFF
        self.assertEqual(self.Parse(bytes(data)).processResult, Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR)


if __name__ == "__main__":
    unittest.main()
