"""The DFM protocol: instruction bytes, firmware versions and Status record parsing."""
import support  # noqa: F401  (must come first)

import datetime
import struct
import unittest

import COMM
import DataGetter
import Enums
import Instruction
import Paradigm
import StatusPacket
from StatusPacket import Checksum32

# Shared with DFMV3_V2 tests/test_ledcontrol.c: both sides must agree on these bytes.
GOLDEN_INSTRUCTION = ("05f701020401010028000800640003000001f400000000000000010000000a000000c8"
                      "0014fffeffff001e03ff03ff03ff03ff03ff03ff03ff03fffffff05f")


def PR10():
    items = [("Type", "ProgressiveRatio", 2), ("ActivationMs", "500", 3), ("Step", "10", 4), ("Cap", "200", 5),
             ("Acclimation", "3", 6)]
    return Paradigm.Paradigm.FromSettings("PR10", items, 1)


def Record(dfmID=5, index=7, number=258, paradigmType=4, phases=0x001, wells=None, onMs=None, activations=None,
           requirement=None, progress=None):
    """A 127-byte Status record laid out as firmware 4.0.0 sends it (PacketManager.h)."""
    wells = wells or [100 + w for w in range(12)]
    body = bytes([dfmID, 0]) + struct.pack(">HBH", number, paradigmType, phases)
    body += struct.pack(">12H", *wells) + struct.pack(">HH", 512, 0x003)
    body += bytes(onMs or [w for w in range(12)])
    body += struct.pack(">12H", *(activations or [w * 2 for w in range(12)]))
    body += struct.pack(">12H", *(requirement or [10] * 12))
    body += struct.pack(">12H", *(progress or [3] * 12))
    body += struct.pack(">I", index)
    return body + Checksum32(body).to_bytes(4, "big")


class Instructions(unittest.TestCase):
    def test_golden_paradigm_instruction(self):
        instruct = Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10())
        instruct.SetOptoValues([20, Instruction.ON, Instruction.OFF, 30] + [1023] * 8)
        packet = bytes([5, COMM.PARADIGM_INSTRUCTION_REQUEST]) + COMM.ParadigmInstructionPayload(instruct, 258, True)
        frame = packet + Checksum32(packet).to_bytes(4, "big")
        self.assertEqual(frame.hex(), GOLDEN_INSTRUCTION)

    def test_baseline_moves_thresholds_not_on_off(self):
        instruct = Instruction.DFMInstruction(Enums.DARKSTATE.OFF, PR10())
        instruct.SetOptoValues([20, Instruction.ON, Instruction.OFF] + [Instruction.OFF] * 9)
        instruct.SetBaseline([100] * 12)
        payload = COMM.ParadigmInstructionPayload(instruct, 1, False)
        self.assertEqual(struct.unpack(">3H", payload[33:39]), (120, COMM.THRESHOLD_ON, COMM.THRESHOLD_OFF))

    def test_old_firmware_gets_old_settings(self):
        nonFeeding = Paradigm.Paradigm.FromSettings("NF", [("Type", "NonFeeding", 2), ("OnDelayMs", "500", 3)], 1)
        instruct = Instruction.DFMInstruction(Enums.DARKSTATE.OFF, nonFeeding)
        payload = COMM.InstructionPayload(instruct, 4)
        frequency, pulseWidth, decay, delay, maxTimeOn = struct.unpack(">HHIII", payload[1:17])
        self.assertEqual((frequency, pulseWidth, decay, delay, maxTimeOn), (40, 8 | 0x8000, 0xFFFFFFFF, 500, 0))

    def test_firmware_versions(self):
        self.assertEqual(COMM.FirmwareVersionTuple(b"4.0.0"), (4, 0, 0))
        self.assertEqual(COMM.FirmwareVersionTuple("3.5.0"), (3, 5, 0))
        self.assertEqual(COMM.FirmwareVersionTuple("junk"), ())
        self.assertTrue(COMM.UsesParadigmFirmware("4.0.0"))
        self.assertFalse(COMM.UsesParadigmFirmware(b"3.5.0"))
        self.assertTrue(COMM.SupportsPartialAck("3.5.0"))
        self.assertFalse(COMM.SupportsPartialAck(COMM.LEGACY_VERSION))


class Records(unittest.TestCase):
    def Parse(self, data, i=0):
        sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
        sp.ProcessStatusPacket(data, datetime.datetime(2026, 1, 1), i, StatusPacket.V4_PACKET_SIZE)
        return sp

    def test_v4_record(self):
        sp = self.Parse(Record(activations=[65535] + [1] * 11, onMs=[200] + [0] * 11))
        self.assertEqual(sp.processResult, Enums.PROCESSEDPACKETRESULT.OKAY)
        self.assertTrue(sp.isV4)
        self.assertEqual((sp.instructionNumber, sp.paradigmType, sp.recordIndex), (258, 4, 7))
        self.assertEqual(sp.phases[:3], [1, 0, 0])
        self.assertEqual(list(sp.analogValues[:2]), [100, 101])
        self.assertAlmostEqual(sp.voltsIn, 3.3)
        self.assertEqual(sp.optoState1, 0x003)
        self.assertEqual((sp.onMs[0], sp.activationsRaw[0], sp.requirement[0], sp.progress[0]), (200, 65535, 10, 3))

    def test_checksum(self):
        data = bytearray(Record())
        data[50] ^= 1
        self.assertEqual(self.Parse(bytes(data)).processResult, Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR)

    def test_v3_training_flag_dropped(self):
        body = bytes([5, 0]) + (0x800000 | (500 << 7)).to_bytes(3, "big") + bytes(33) + bytes(9) + (1).to_bytes(4, "big")
        data = body + Checksum32(body).to_bytes(4, "big")
        sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
        sp.ProcessStatusPacket(data, datetime.datetime(2026, 1, 1))
        self.assertEqual(sp.analogValues[0], 500)

    def test_data_line_matches_header(self):
        columns = len((StatusPacket.DATA_COLUMNS + "," + StatusPacket.PARADIGM_COLUMNS).split(","))
        v4 = self.Parse(Record())
        v4.interval, v4.cycle, v4.paradigmName, v4.activationTotals = 0, 2, "PR10", [5] * 12
        line = v4.GetDataBufferPrintPacket().rstrip("\n").split(",")
        self.assertEqual(len(line), columns)
        tail = line[len(StatusPacket.DATA_COLUMNS.split(",")):]
        self.assertEqual(tail[:4], ["1", "2", "PR10", "A"])
        self.assertEqual(tail[3 + 12 + 12], "10")
        old = StatusPacket.StatusPacket(1, 5, Enums.DFMTYPE.PLETCHERV3)
        self.assertEqual(len(old.GetDataBufferPrintPacket().rstrip("\n").split(",")), columns)
        envmon = StatusPacket.StatusPacket(1, 99, Enums.DFMTYPE.ENVMONV3)
        self.assertEqual(len(envmon.GetDataBufferPrintPacket().split(",")), len(StatusPacket.DATA_COLUMNS.split(",")))

    def test_requirement_blank_for_other_types(self):
        sp = self.Parse(Record(paradigmType=1))
        tail = sp.GetDataBufferPrintPacket().rstrip("\n").split(",")[len(StatusPacket.DATA_COLUMNS.split(",")):]
        self.assertEqual(tail[3 + 24:3 + 48], [""] * 24)

    def test_reader_uses_the_firmware_record_size(self):
        getter = object.__new__(DataGetter.DataGetter)
        getter.firmwareVersions = {5: b"4.0.0"}
        getter.startTime = datetime.datetime(2026, 1, 1)
        getter.currentReadIndex = 1
        getter.EnvMonV3_Temperature = getter.EnvMonV3_Humidity = getter.EnvMonV3_LUX = 0.0
        info = DataGetter.DFMInfo(5, Enums.DFMTYPE.PLETCHERV3)
        packets = getter.ProcessPacket(info, Enums.COBSRESULT.OKAY, Record(index=1) + Record(index=2), None)
        self.assertEqual([(p.isV4, p.recordIndex, p.processResult) for p in packets],
                         [(True, 1, Enums.PROCESSEDPACKETRESULT.OKAY), (True, 2, Enums.PROCESSEDPACKETRESULT.OKAY)])
        getter.firmwareVersions = {5: b"3.5.0"}
        packets = getter.ProcessPacket(info, Enums.COBSRESULT.OKAY, Record(index=1), None)
        self.assertEqual(packets[0].processResult, Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES)


if __name__ == "__main__":
    unittest.main()
