"""The DFM protocol: instruction bytes for each firmware generation, firmware versions and Status
record parsing. Shared with DFMV3_V2 (tests/test_ledcontrol.c, src/UART2.c, src/PacketManager.h):
both sides must agree on these bytes."""
import support  # noqa: F401  (must come first)

import datetime
import queue
import struct
import time
import unittest

import COMM
import DataGetter
import DFMErrors
import Enums
import Instruction
import Paradigm
import StatusPacket
from StatusPacket import Checksum32

# Shared with DFMV3_V2 tests/test_ledcontrol.c: both sides must agree on these bytes.
GOLDEN_INSTRUCTION = ("05f701020401010028000800640003000001f400000000000000010000000a000000c8"
                      "0014fffeffff001e03ff03ff03ff03ff03ff03ff03ff03fffffff05f")
# The old instruction (0xFD) for firmware before 4.0.0, derived with struct: ID 5, dark on, 40 Hz,
# 8 ms, ClosedLoop with HoldMs 1000 and MaxOnMs 2000, thresholds 20, On, Off, 30, then eight at
# 1023. Firmware 1.0.5 takes 2-byte times (41 bytes), 2.0.0 and later 4-byte times (47 bytes).
GOLDEN_1_0_5 = "05fd010028000803e8000007d000140000ffff001e03ff03ff03ff03ff03ff03ff03ff03fffffff2cb"
GOLDEN_2_0_0 = "05fd0100280008000003e800000000000007d000140000ffff001e03ff03ff03ff03ff03ff03ff03ff03fffffff2cb"


def PR10():
    items = [("Type", "ProgressiveRatio", 2), ("ActivationMs", "500", 3), ("Step", "10", 4), ("Cap", "200", 5),
             ("Acclimation", "3", 6)]
    return Paradigm.Paradigm.FromSettings("PR10", items, 1)


def ClosedLoop():
    paradigm = Paradigm.Paradigm("CL", Paradigm.ParadigmType.CLOSEDLOOP, {"HoldMs": 1000, "MaxOnMs": 2000})
    instruct = Instruction.DFMInstruction(Enums.DARKSTATE.ON, paradigm)
    instruct.SetOptoValues([20, Instruction.ON, Instruction.OFF, 30] + [1023] * 8)
    return instruct


def OldFrame(instruct, timingSize, dfmID=5):
    packet = bytes([dfmID, COMM.INSTRUCTION_REQUEST]) + COMM.InstructionPayload(instruct, timingSize)
    return packet + Checksum32(packet).to_bytes(4, "big")


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


def Record56(dfmID=5, index=7, errorFlags=0, wells=None, training=(), frequency=40, pulseWidth=8, dark=1):
    """A 56-byte Status record as firmware 1.0.5 to 3.5.0 sends it (PacketManager.h): each Well a
    3-byte sum of 128 scans, which PyMCU shifts right by 7. From 2.0.0 the top bit of a Well is set
    while it is in training; PyMCU drops it."""
    wells = wells or [100 + w for w in range(12)]
    body = bytes([dfmID, errorFlags])
    for w, value in enumerate(wells):
        body += ((value << 7) | (0x800000 if w in training else 0)).to_bytes(3, "big")
    body += (512 << 7).to_bytes(3, "big")   # supply voltage reading
    body += struct.pack(">HHHB", 0x0003, frequency, pulseWidth, dark)
    body += struct.pack(">I", index)
    return body + Checksum32(body).to_bytes(4, "big")


class Instructions(unittest.TestCase):
    def test_golden_paradigm_instruction(self):
        instruct = Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10())
        instruct.SetOptoValues([20, Instruction.ON, Instruction.OFF, 30] + [1023] * 8)
        packet = bytes([5, COMM.PARADIGM_INSTRUCTION_REQUEST]) + COMM.ParadigmInstructionPayload(instruct, 258, True)
        frame = packet + Checksum32(packet).to_bytes(4, "big")
        self.assertEqual(frame.hex(), GOLDEN_INSTRUCTION)

    def test_golden_old_frames(self):
        self.assertEqual(OldFrame(ClosedLoop(), 2).hex(), GOLDEN_1_0_5)
        self.assertEqual(OldFrame(ClosedLoop(), 4).hex(), GOLDEN_2_0_0)
        self.assertEqual((len(bytes.fromhex(GOLDEN_1_0_5)), len(bytes.fromhex(GOLDEN_2_0_0))), (41, 47))

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

    def test_firmware_needed_per_generation(self):
        nonFeeding = Paradigm.Paradigm.FromSettings("NF", [("Type", "NonFeeding", 2), ("OnDelayMs", "500", 3)], 1)
        hold70 = Paradigm.Paradigm("Hold70", Paradigm.ParadigmType.CLOSEDLOOP, {"HoldMs": 70000})
        closedLoop = ClosedLoop().paradigm
        for paradigm in (nonFeeding, hold70, closedLoop):
            self.assertIsNone(paradigm.FirmwareNeeded())
            self.assertIsNone(paradigm.FirmwareNeeded((2, 0, 1)))
            self.assertIsNone(paradigm.FirmwareNeeded((4, 0, 0)))
        self.assertIsNone(closedLoop.FirmwareNeeded((1, 0, 5)))
        self.assertEqual(nonFeeding.FirmwareNeeded((1, 0, 5)), "the NonFeeding Paradigm type needs firmware 2.0.0")
        self.assertEqual(hold70.FirmwareNeeded((1, 0, 5)), "times above 65535 ms need firmware 2.0.0")
        for version in (None, (1, 0, 5), (3, 5, 0)):
            self.assertEqual(PR10().FirmwareNeeded(version), "the ProgressiveRatio Paradigm type needs firmware 4.0.0")


class Versions(unittest.TestCase):
    def test_firmware_versions(self):
        self.assertEqual(COMM.FirmwareVersionTuple(b"4.0.0"), (4, 0, 0))
        self.assertEqual(COMM.FirmwareVersionTuple("3.5.0"), (3, 5, 0))
        self.assertEqual(COMM.FirmwareVersionTuple(b"2.0.1"), (2, 0, 1))
        self.assertEqual(COMM.FirmwareVersionTuple("junk"), ())
        self.assertEqual(COMM.FirmwareVersionTuple(None), ())
        self.assertTrue(COMM.UsesParadigmFirmware("4.0.0"))
        self.assertFalse(COMM.UsesParadigmFirmware(b"3.5.0"))

    def test_partial_ack_from_3_5_0(self):
        self.assertFalse(COMM.SupportsPartialAck(COMM.LEGACY_VERSION))
        self.assertFalse(COMM.SupportsPartialAck(b"2.0.1"))
        self.assertFalse(COMM.SupportsPartialAck(b"2.0.2"))   # a 2.0.x hotfix would not have it
        self.assertTrue(COMM.SupportsPartialAck("3.5.0"))
        self.assertTrue(COMM.SupportsPartialAck("4.0.0"))

    def test_error_labels_per_firmware(self):
        before, after = DFMErrors.V3_ERROR_DISPLAY_BEFORE_3_5_0, DFMErrors.V3_ERROR_DISPLAY
        for version in ("1.0.5", "2.0.0", "2.0.1", "2.0.2"):
            self.assertIs(DFMErrors.V3ErrorDisplay(version), before, version)
        for version in ("3.5.0", "4.0.0"):
            self.assertIs(DFMErrors.V3ErrorDisplay(version), after, version)
        self.assertEqual((before[0][0], before[0][2], before[1]), ("No Ack", (0, 1), None))
        self.assertEqual((after[0][2], after[1][0], after[1][2]), ((0,), "Overflow", (1,)))


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

    def test_v3_record(self):
        sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
        sp.ProcessStatusPacket(Record56(index=7, errorFlags=0x01, training=(0,)), datetime.datetime(2026, 1, 1))
        self.assertEqual(sp.processResult, Enums.PROCESSEDPACKETRESULT.OKAY)
        self.assertFalse(sp.isV4)
        self.assertEqual((sp.recordIndex, sp.errorFlags, sp.darkStatus, sp.optoFrequency, sp.optoPulseWidth), (7, 1, 1, 40, 8))
        self.assertEqual(list(sp.analogValues), [100 + w for w in range(12)])   # the training flag is dropped
        self.assertEqual(sp.packetTime, datetime.datetime(2026, 1, 1, 0, 0, 1, 400000))
        data = bytearray(Record56())
        data[5] ^= 0xFF
        sp.ProcessStatusPacket(bytes(data), datetime.datetime(2026, 1, 1))
        self.assertEqual(sp.processResult, Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR)

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
        oldLine = old.GetDataBufferPrintPacket().rstrip("\n").split(",")
        self.assertEqual(len(oldLine), columns)
        self.assertEqual(set(oldLine[len(StatusPacket.DATA_COLUMNS.split(",")):]), {"NA"})
        envmon = StatusPacket.StatusPacket(1, 99, Enums.DFMTYPE.ENVMONV3)
        self.assertEqual(len(envmon.GetDataBufferPrintPacket().split(",")), len(StatusPacket.DATA_COLUMNS.split(",")))

    def test_requirement_na_for_other_types(self):
        sp = self.Parse(Record(paradigmType=1))
        tail = sp.GetDataBufferPrintPacket().rstrip("\n").split(",")[len(StatusPacket.DATA_COLUMNS.split(",")):]
        self.assertEqual(tail[3 + 24:3 + 48], ["NA"] * 24)

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
        packets = getter.ProcessPacket(info, Enums.COBSRESULT.OKAY, Record56(index=1) + Record56(index=2), None)
        self.assertEqual([(p.isV4, p.recordIndex, p.processResult) for p in packets],
                         [(False, 1, Enums.PROCESSEDPACKETRESULT.OKAY), (False, 2, Enums.PROCESSEDPACKETRESULT.OKAY)])

    def test_record_size_gives_away_a_misread_version(self):
        # A 4.0.0 board whose version reply was lost is taken for 1.0.5. Its 127-byte records
        # make the reader ask again, and the read that showed it isn't lost.
        getter = MakeGetter({5: COMM.LEGACY_VERSION}, FakeCOMM(versions=[b"4.0.0"]))
        info = DataGetter.DFMInfo(5, Enums.DFMTYPE.PLETCHERV3)
        packets = getter.ProcessPacket(info, Enums.COBSRESULT.OKAY, Record(index=1) + Record(index=2), None)
        self.assertEqual([(p.isV4, p.processResult) for p in packets], [(True, Enums.PROCESSEDPACKETRESULT.OKAY)] * 2)
        self.assertEqual(getter.firmwareVersions[5], b"4.0.0")
        # If it still doesn't answer, the read fails and the next one tries again.
        getter = MakeGetter({5: COMM.LEGACY_VERSION}, FakeCOMM(versions=[COMM.LEGACY_VERSION]))
        packets = getter.ProcessPacket(info, Enums.COBSRESULT.OKAY, Record(index=1), None)
        self.assertEqual(packets[0].processResult, Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES)
        # 56-byte records from a board known as 4.0.0 (swapped since) are believed over the old
        # version, even when the new board doesn't answer.
        getter = MakeGetter({5: b"4.0.0"}, FakeCOMM(versions=[COMM.LEGACY_VERSION]))
        packets = getter.ProcessPacket(info, Enums.COBSRESULT.OKAY, Record56(index=1), None)
        self.assertEqual(packets[0].processResult, Enums.PROCESSEDPACKETRESULT.OKAY)
        self.assertEqual(getter.firmwareVersions[5], COMM.LEGACY_VERSION)


class FakeCOMM:
    """Records what the reader sends. Version requests are answered from a list."""
    def __init__(self, versions=(), statusReplies=()):
        self.calls = []
        self.versions = list(versions)
        self.statusReplies = list(statusReplies)

    def GetVersion(self, ID):
        self.calls.append(("GetVersion", ID))
        return self.versions.pop(0)

    def GetStatusPacket(self, ID, DFMType, latestOnly, recordSize):
        self.calls.append(("GetStatusPacket", ID, recordSize))
        return Enums.COBSRESULT.OKAY, self.statusReplies.pop(0)

    def __getattr__(self, name):
        def Call(*args):
            self.calls.append((name,) + args)
            return True
        return Call


def MakeGetter(versions, comm):
    getter = object.__new__(DataGetter.DataGetter)
    getter.firmwareVersions = dict(versions)
    getter.theCOMM = comm
    getter.startTime = datetime.datetime(2026, 1, 1)
    getter.currentReadIndex = 1
    getter.EnvMonV3_Temperature = getter.EnvMonV3_Humidity = getter.EnvMonV3_LUX = 0.0
    getter.bufferResetCounts, getter.bufferResetTimes = {}, {}
    getter.busGeneration, getter.isPaused, getter.getLatestStatusOnly = 0, False, False
    getter.command_q, getter.answer_q, getter.data_q = queue.Queue(), queue.Queue(), queue.Queue()
    return getter


class Reader(unittest.TestCase):
    def test_version_request_asked_again_only_when_garbled(self):
        comm = object.__new__(COMM.UARTCOMM)
        replies = []
        comm._ReadFrame = lambda maxBytes, timeout: replies.pop(0)
        sent = []
        comm._SendRequest = lambda ID, command: sent.append(command)
        garbled = (Enums.COBSRESULT.INCOMPLETEPACKET, b"")
        replies[:] = [garbled, (Enums.COBSRESULT.OKAY, b"4\x00.0"), (Enums.COBSRESULT.OKAY, b"4.0.0")]
        self.assertEqual(comm.GetVersion(5), b"4.0.0")
        self.assertEqual(len(sent), 3)
        # A 1.0.5 board never answers: asked once, as each request is an error on that board.
        sent.clear()
        replies[:] = [(Enums.COBSRESULT.NOANSWER, b"")]
        self.assertEqual(comm.GetVersion(5), COMM.LEGACY_VERSION)
        self.assertEqual(len(sent), 1)
        replies[:] = [garbled] * COMM.VERSION_ATTEMPTS
        self.assertIsNone(comm.GetVersion(5))

    def test_known_version_kept_when_unanswered(self):
        getter = MakeGetter({5: b"4.0.0"}, FakeCOMM(versions=[COMM.LEGACY_VERSION, None, b"4.0.1"]))
        self.assertEqual(getter._ReadVersion(5), b"4.0.0")
        self.assertIsNone(getter._ReadVersion(5))
        self.assertEqual(getter.firmwareVersions[5], b"4.0.0")
        self.assertEqual(getter._ReadVersion(5), b"4.0.1")
        # Not known yet: no answer means 1.0.5.
        getter = MakeGetter({}, FakeCOMM(versions=[COMM.LEGACY_VERSION]))
        self.assertEqual(getter._ReadVersion(7), COMM.LEGACY_VERSION)

    def test_partial_ack_names_the_last_packet_from_3_5_0(self):
        info = DataGetter.DFMInfo(5, Enums.DFMTYPE.PLETCHERV3)
        for version, expected in ((b"4.0.0", [("SendPartialAck", 5, 2)]), (b"3.0.0", [("SendAck", 5)])):
            getter = MakeGetter({5: version}, FakeCOMM())
            size = StatusPacket.V4_PACKET_SIZE if version == b"4.0.0" else StatusPacket.V3_PACKET_SIZE
            body = (Record(index=1) + Record(index=2)) if size == StatusPacket.V4_PACKET_SIZE else (Record56(index=1) + Record56(index=2))
            getter._Acknowledge(info, getter.ProcessPacket(info, Enums.COBSRESULT.OKAY, body, None))
            self.assertEqual(getter.theCOMM.calls, expected)
        # A failed read isn't acknowledged at all.
        getter = MakeGetter({5: b"4.0.0"}, FakeCOMM())
        getter._Acknowledge(info, getter.ProcessPacket(info, Enums.COBSRESULT.NOANSWER, b"", None))
        self.assertEqual(getter.theCOMM.calls, [])

    def test_commands_go_out_between_reads(self):
        comm = FakeCOMM(statusReplies=[Record(dfmID=5, index=1), Record(dfmID=6, index=1)])
        getter = MakeGetter({5: b"4.0.0", 6: b"4.0.0"}, comm)
        getter.bufferResetTimes = {5: time.monotonic() - 10}
        getter.command_q.put(DataGetter.MP_Command(Enums.COMMANDTYPE.LINKAGE, [6, list(range(12))], 1))
        getter.ReadValues([DataGetter.DFMInfo(5, Enums.DFMTYPE.PLETCHERV3), DataGetter.DFMInfo(6, Enums.DFMTYPE.PLETCHERV3)])
        self.assertEqual([c[:2] for c in comm.calls],
                         [("GetStatusPacket", 5), ("SendPartialAck", 5), ("SendLinkage", 6),
                          ("GetStatusPacket", 6), ("SendPartialAck", 6)])
        self.assertEqual(comm.calls[0][2], StatusPacket.V4_PACKET_SIZE)
        first = getter.data_q.get_nowait()[0]
        self.assertFalse(first.isFullReply)
        self.assertAlmostEqual(first.secondsSinceReset, 10, delta=1)
        self.assertIsNone(getter.data_q.get_nowait()[0].secondsSinceReset)


if __name__ == "__main__":
    unittest.main()
