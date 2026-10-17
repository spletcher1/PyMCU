"""DFM bookkeeping: instruction numbers, keeping Paradigm state, Activation totals, what each
firmware generation is sent, and the checks before a Program starts."""
import support  # noqa: F401  (must come first)

import csv
import datetime
import io
import os
import time
import unittest

import COMM
import DFM
import DFMErrors
import DFMGroup
import Enums
import Instruction
import Message
import MessagesList
import Paradigm
import Program
from test_protocol import PR10, Record, Record56, ClosedLoop

import StatusPacket

MESSAGES = []
DFM.DFM.DFM_message += MESSAGES.append
WELLS = "20,Off,20,Off,20,Off,20,Off,20,Off,20,Off"


class FakeMP:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def Call(*args):
            self.calls.append((name,) + args)
            return True
        return Call


class ProbeMP(FakeMP):
    """Also answers the version request with what it was given, as DataGetter would."""
    def __init__(self, version):
        super().__init__()
        self.version = version

    def GetVersion(self, ID):
        self.calls.append(("GetVersion", ID))
        return self.version


def MakeDFM(version="4.0.0"):
    d = DFM.DFM(5, Enums.DFMTYPE.PLETCHERV3, FakeMP())
    d.firmwareVersion = version
    d.DFMSubType = Enums.DFMSUBTYPE.V2
    d.isVersionGetNeeded = False
    d.status = Enums.CURRENTSTATUS.RECORDING
    return d


def MakeProbedDFM(version=b"2.0.1", ID=5):
    """A DFM that learned its firmware the real way, from the version request."""
    d = DFM.DFM(ID, Enums.DFMTYPE.PLETCHERV3, ProbeMP(version))
    d.ReadFirmwareVersion()
    d.status = Enums.CURRENTSTATUS.RECORDING
    return d


def Sent(d):
    return [c for c in d.MP.calls if c[0].startswith("SendInstruction") or c[0] == "SendParadigmInstruction"]


def Refusals(dfmID):
    return [m for m in MESSAGES if m.DFMId == dfmID and "can't run" in m.message]


def NonFeeding():
    return Paradigm.Paradigm.FromSettings("NF", [("Type", "NonFeeding", 2), ("OnDelayMs", "500", 3)], 1)


def Packet56(errorFlags=0, index=1):
    sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
    sp.ProcessStatusPacket(Record56(index=index, errorFlags=errorFlags), datetime.datetime(2026, 1, 1))
    return sp


class Instructions(unittest.TestCase):
    def test_numbers_and_keeping_state(self):
        d = MakeDFM()
        pr = Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10())
        other = Instruction.DFMInstruction()
        d.UpdateInstruction(pr, False, 0, 1)
        d.CheckStatusV3()
        d.UpdateInstruction(pr, False, 0, 1)        # unchanged: not sent again
        d.CheckStatusV3()
        d.UpdateInstruction(pr, False, 0, 2)        # next Cycle: same Paradigm
        d.CheckStatusV3()
        d.UpdateInstruction(other, False, 1, 2)     # another Paradigm
        d.CheckStatusV3()
        sent = Sent(d)
        self.assertEqual([c[0] for c in sent], ["SendParadigmInstruction"] * 3)
        numbers = [c[3] for c in sent]
        self.assertEqual(numbers[1], numbers[0] % 0xFFFF + 1)
        self.assertEqual([c[4] for c in sent], [False, True, False])
        self.assertEqual(d.instructionInfo[numbers[1]].cycle, 2)

    def test_old_firmware(self):
        d = MakeDFM("3.5.0")
        d.UpdateInstruction(Instruction.DFMInstruction(), False, 0, 1)
        d.CheckStatusV3()
        self.assertEqual(Sent(d)[0][0], "SendInstructionDFMV2_0")
        MESSAGES.clear()
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 1, 1)
        d.CheckStatusV3()
        self.assertEqual(len(Sent(d)), 1)
        self.assertEqual(len(Refusals(5)), 1)
        self.assertIn("4.0.0", Refusals(5)[0].message)


class Generations(unittest.TestCase):
    def test_1_0_5_board(self):
        d = MakeProbedDFM(COMM.LEGACY_VERSION)
        self.assertEqual(d.firmwareVersion, "1.0.5")
        self.assertEqual(d.DFMSubType, Enums.DFMSUBTYPE.V1_0_5)
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY_BEFORE_3_5_0)
        d.UpdateInstruction(ClosedLoop(), False, 0, 1)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV1_0_5"])

    def test_2_0_1_board(self):
        d = MakeProbedDFM(b"2.0.1")
        self.assertEqual(d.DFMSubType, Enums.DFMSUBTYPE.V2)
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY_BEFORE_3_5_0)
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.OFF, NonFeeding()), False, 0, 1)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV2_0"])

    def test_3_5_0_and_4_0_0_boards(self):
        d = MakeProbedDFM(b"3.5.0")
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY)
        d.UpdateInstruction(ClosedLoop(), False, 0, 1)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV2_0"])
        d = MakeProbedDFM(b"4.0.0")
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY)
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 0, 1)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendParadigmInstruction"])

    def test_1_0_5_board_refuses_what_it_would_misread(self):
        MESSAGES.clear()
        d = MakeProbedDFM(COMM.LEGACY_VERSION)
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.OFF, NonFeeding()), False, 0, 1)
        d.CheckStatusV3()
        self.assertEqual(Sent(d), [])
        self.assertEqual(len(Refusals(5)), 1)
        self.assertIn("NonFeeding", Refusals(5)[0].message)
        self.assertIn("2.0.0", Refusals(5)[0].message)
        self.assertEqual(Refusals(5)[0].messageType, Enums.MESSAGETYPE.ERROR)
        d.CheckStatusV3()                     # not repeated on the next pass
        self.assertEqual(len(Refusals(5)), 1)
        hold70 = Paradigm.Paradigm("Hold70", Paradigm.ParadigmType.CLOSEDLOOP, {"HoldMs": 70000})
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.OFF, hold70), False, 1, 1)
        d.CheckStatusV3()
        self.assertEqual(Sent(d), [])
        self.assertIn("65535", Refusals(5)[-1].message)
        d.UpdateInstruction(ClosedLoop(), False, 2, 1)   # a plain Interval still goes out
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV1_0_5"])

    def test_probe_error_masked_once_on_1_0_5(self):
        d = MakeProbedDFM(COMM.LEGACY_VERSION)
        d.UpdateReportedValues([Packet56(errorFlags=0x04, index=1)], False)
        self.assertEqual(d.currentDFMErrors.GetStatus((2,)), Enums.REPORTEDERRORSTATUS.NEVER)
        d.UpdateReportedValues([Packet56(errorFlags=0x04, index=2)], False)   # a real one shows
        self.assertEqual(d.currentDFMErrors.GetStatus((2,)), Enums.REPORTEDERRORSTATUS.CURRENT)
        d.ReadFirmwareVersion()                                               # each probe sets it again
        self.assertTrue(d.maskProbeError)
        d = MakeProbedDFM(b"2.0.1")           # a board that answered wasn't asked anything it can't take
        d.UpdateReportedValues([Packet56(errorFlags=0x04)], False)
        self.assertEqual(d.currentDFMErrors.GetStatus((2,)), Enums.REPORTEDERRORSTATUS.CURRENT)


class Records(unittest.TestCase):
    def Packets(self, d, index, activations, resetCount=0):
        sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
        sp.ProcessStatusPacket(Record(index=index, number=d.instructionNumber, activations=activations),
                               datetime.datetime(2026, 1, 1), 0, StatusPacket.V4_PACKET_SIZE)
        sp.bufferResetCount = resetCount
        return [sp]

    def test_paradigm_columns_and_totals(self):
        d = MakeDFM()
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 3, 2)
        d.ProcessPackets(self.Packets(d, 1, [65530] * 12), True)
        d.ProcessPackets(self.Packets(d, 2, [4] * 12), True)
        last = d.theData.GetLastDataPoint()
        self.assertEqual((last.interval, last.cycle, last.paradigmName), (3, 2, "PR10"))
        self.assertEqual((last.optoFrequency, last.darkStatus), (40, 1))
        self.assertEqual(last.activationTotals[0], 65540)
        # A buffer reset starts the totals again.
        d.ProcessPackets(self.Packets(d, 1, [2] * 12, resetCount=1), True)
        self.assertEqual(d.theData.GetLastDataPoint().activationTotals[0], 2)

    def Columns(self, d):
        line = d.theData.GetLastDataPoint().GetDataBufferPrintPacket().rstrip("\n").split(",")
        return line[len(StatusPacket.DATA_COLUMNS.split(",")):][:3]

    def test_baseline_records_are_interval_0(self):
        d = MakeDFM()
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.OFF), False)   # idle, outside the Program
        d.ProcessPackets(self.Packets(d, 1, [0] * 12), True)
        self.assertEqual(self.Columns(d), ["0", "NA", "Idle"])
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 0, 1)
        d.ProcessPackets(self.Packets(d, 2, [0] * 12), True)
        self.assertEqual(self.Columns(d), ["1", "1", "PR10"])
        # Once the Program has run, an instruction outside it has no Interval.
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.OFF), False)
        d.ProcessPackets(self.Packets(d, 3, [0] * 12), True)
        self.assertEqual(self.Columns(d), ["NA", "NA", "Idle"])
        # A buffer reset (the next recording) starts with a baseline again.
        d.ProcessPackets(self.Packets(d, 1, [0] * 12, resetCount=1), True)
        self.assertEqual(self.Columns(d), ["0", "NA", "Idle"])


def V4Packets(d, indexes, full=False, since=None, activations=None, resetCount=0):
    """One read's packets, as the reader hands them over."""
    packets = []
    for i in indexes:
        sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
        sp.ProcessStatusPacket(Record(index=i, number=d.instructionNumber, activations=activations),
                               datetime.datetime(2026, 1, 1), 0, StatusPacket.V4_PACKET_SIZE)
        sp.bufferResetCount, sp.isFullReply, sp.secondsSinceReset = resetCount, full, since
        packets.append(sp)
    return packets


def Stored(d):
    """(Index, seconds into the recording) of each buffered data-file line."""
    rows = [line.split(",") for line in d.theData.theData]
    times = [datetime.datetime.strptime(r[0] + " " + r[1], "%m/%d/%Y %H:%M:%S") + datetime.timedelta(milliseconds=float(r[2]))
             for r in rows]
    return [(int(r[26]), round((t - datetime.datetime(2026, 1, 1)).total_seconds(), 1)) for r, t in zip(rows, times)]


def Texts(dfmID=5):
    return [m.message for m in MESSAGES if m.DFMId == dfmID]


class Integrity(unittest.TestCase):
    def setUp(self):
        MESSAGES.clear()
        self.d = MakeDFM()
        self.d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 0, 1)
        self.d.CheckStatusV3()

    def test_restart_mid_recording(self):
        d = self.d
        d.ProcessPackets(V4Packets(d, range(1, 301), activations=[10] * 12), True)
        self.assertEqual(Stored(d)[-1], (300, 60.0))
        d.MP.calls.clear()
        # Read 100 s into the recording: the DFM restarted and has records 1 to 5 since.
        d.ProcessPackets(V4Packets(d, range(1, 6), since=100.0, activations=[2] * 12), True)
        self.assertEqual(Stored(d)[-5:], [(496, 99.2), (497, 99.4), (498, 99.6), (499, 99.8), (500, 100.0)])
        self.assertEqual(d.activationTotals[0], 12)          # carried on, no wrap-around jump
        # Its Interval (with fresh Paradigm state) and linkage went out again at once.
        self.assertEqual([(c[0], c[4]) for c in Sent(d)], [("SendParadigmInstruction", False)])
        self.assertIn("SendLinkage", [c[0] for c in d.MP.calls])
        texts = Texts()
        self.assertTrue(any("restarted" in t and "from 300 to 1" in t for t in texts))
        self.assertTrue(any("Index 301 to 495 are missing" in t for t in texts))
        self.assertFalse(any("Repeated" in t for t in texts))
        # Later records carry on with the offset.
        d.ProcessPackets(V4Packets(d, [6], since=100.2, activations=[2] * 12), True)
        self.assertEqual(Stored(d)[-1], (501, 100.2))

    def test_restart_held_until_a_reply_that_isnt_full(self):
        d = self.d
        d.ProcessPackets(V4Packets(d, range(1, 301)), True)
        d.ProcessPackets(V4Packets(d, range(1, 29), full=True, since=100.0), True)
        self.assertEqual(len(Stored(d)), 300)                # held: more are waiting on the DFM
        d.ProcessPackets(V4Packets(d, range(29, 41), since=100.1), True)
        self.assertEqual(Stored(d)[300], (461, 92.2))
        self.assertEqual(Stored(d)[-1], (500, 100.0))
        # Held records go in when the recording ends, following straight on.
        d = MakeDFM()
        d.ProcessPackets(V4Packets(d, range(1, 301)), True)
        d.ProcessPackets(V4Packets(d, range(1, 4), full=True, since=100.0), True)
        d.FlushPendingRecords()
        self.assertEqual([i for i, _ in Stored(d)[-3:]], [301, 302, 303])

    def test_resend_is_not_a_restart(self):
        d = self.d
        d.ProcessPackets(V4Packets(d, range(1, 301)), True)
        d.ProcessPackets(V4Packets(d, range(273, 306), since=61.0), True)  # ACK lost: 273-300 again
        self.assertEqual([i for i, _ in Stored(d)[-6:]], [300, 301, 302, 303, 304, 305])
        self.assertFalse(any("restarted" in t for t in Texts()))

    def test_full_buffer_reported_once_with_what_was_lost(self):
        d = self.d
        d.theData.maxSize = 3
        d.ProcessPackets(V4Packets(d, range(1, 7)), True)
        self.assertEqual(len([t for t in Texts() if "data buffer is full" in t]), 1)
        d.theData.RemoveRecords(3)                           # the file could be written again
        d.ProcessPackets(V4Packets(d, [7]), True)
        lost = [t for t in Texts() if "lost 3 records" in t]
        self.assertEqual(len(lost), 1)
        self.assertIn("Index 4 to 6", lost[0])
        self.assertEqual([i for i, _ in Stored(d)], [7])

    def test_one_bad_record_doesnt_lose_the_rest(self):
        d = self.d
        packets = V4Packets(d, range(1, 4))
        packets[1].activationsRaw = None
        d.ProcessPackets(packets, True)
        self.assertEqual([i for i, _ in Stored(d)], [1, 3])
        self.assertEqual(len([t for t in Texts() if "Record 2 couldn't be processed" in t]), 1)

    def test_v4_records_from_a_board_read_as_older(self):
        d = MakeProbedDFM(COMM.LEGACY_VERSION)
        d.MP.version = b"4.0.0"                  # the reader has since read it again
        d.ProcessPackets(V4Packets(d, [1]), True)
        self.assertEqual(d.firmwareVersion, "4.0.0")
        self.assertTrue(any("sent 4.0.0 records" in t for t in Texts()))


class FailingMP(FakeMP):
    """Like FakeMP, but the named commands aren't acknowledged."""
    def __init__(self, failing=()):
        super().__init__()
        self.failing = set(failing)

    def GetVersion(self, ID):
        self.calls.append(("GetVersion", ID))
        return b"4.0.0"

    def __getattr__(self, name):
        def Call(*args):
            self.calls.append((name,) + args)
            return name not in self.failing
        return Call


def Running(d, number, readAfterAck=1.0, full=False):
    """One read whose newest record says the DFM runs instruction number."""
    sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
    sp.ProcessStatusPacket(Record(index=d.lastDFMIndex + 1, number=number), datetime.datetime(2026, 1, 1), 0,
                           StatusPacket.V4_PACKET_SIZE)
    sp.isFullReply, sp.readTime, sp.secondsSinceReset = full, d.ackedInstructionTime + readAfterAck, 1.0
    return [sp]


class Commands(unittest.TestCase):
    def setUp(self):
        MESSAGES.clear()

    def Group(self, failingIDs=()):
        group = object.__new__(DFMGroup.DFMGroup)
        group.theDFMs = {}
        for ID in (1, 2, 3, 4):
            d = MakeDFM()
            d.ID = ID
            d.MP = FailingMP(["SendParadigmInstruction"] if ID in failingIDs else [])
            d.status = Enums.CURRENTSTATUS.UNDEFINED      # as the Program worker leaves them
            group.theDFMs[ID] = d
        group.activeDFM = group.theDFMs[1]
        return group

    def test_program_end_reaches_every_dfm(self):
        group = self.Group(failingIDs=[3])
        for d in group.theDFMs.values():
            d.SetIdleStatus()
        waiting = group.SendPendingCommands(0.2)
        self.assertEqual([d.ID for d in waiting], [3])
        self.assertEqual([len(Sent(d)) for d in group.theDFMs.values()], [1, 1, 1, 1])
        # The read worker keeps trying the one that didn't take it, but not on every pass.
        group.theDFMs[3].MP.failing.clear()
        group._SendWaitingCommands()
        self.assertEqual(len(Sent(group.theDFMs[3])), 1)
        group.theDFMs[3].retryTime = 0
        group._SendWaitingCommands()
        self.assertEqual(len(Sent(group.theDFMs[3])), 2)
        self.assertFalse(group.theDFMs[3].HasPendingCommands())

    def test_toggle_outputs_only_flags_the_dfm_on_screen(self):
        group = self.Group()
        group.activeDFM.SetOutputsOn()
        self.assertTrue(group.activeDFM.isOutputsOn)
        self.assertEqual([d.HasPendingCommands() for d in group.theDFMs.values()], [True, False, False, False])
        # The read worker sends the others nothing: they have nothing waiting.
        group._SendWaitingCommands()
        self.assertEqual([len(Sent(d)) for d in group.theDFMs.values()], [0, 0, 0, 0])
        group.activeDFM.SetOutputsOff()
        self.assertFalse(group.activeDFM.isOutputsOn)

    def test_errors_dont_hold_back_instructions(self):
        d = MakeDFM()
        d.status = Enums.CURRENTSTATUS.ERROR
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 0, 1)
        d.CheckStatus()
        self.assertEqual(len(Sent(d)), 1)
        # A DFM that isn't answering isn't sent anything, and after 10 s that is an error.
        d.status = Enums.CURRENTSTATUS.MISSING
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 1, 1)
        d.CheckStatus()
        self.assertEqual(len(Sent(d)), 1)
        self.assertEqual(Texts(), [])
        d.commandTrouble["instruction"][0] -= 11
        d.CheckStatus()
        d.CheckStatus()
        self.assertEqual(Texts(), ["DFM 5 isn't answering, so its instruction for Interval 2, Cycle 1 hasn't been sent for 11 s. Still trying."])
        d.status = Enums.CURRENTSTATUS.RECORDING
        d.CheckStatus()
        self.assertEqual(len(Sent(d)), 2)
        self.assertIn("acknowledged its instruction for Interval 2, Cycle 1 after 11 s", Texts()[-1])

    def test_repeated_failures_reported_once(self):
        d = MakeDFM()
        d.MP = FailingMP(["SendLinkage"])
        d.isLinkageSetNeeded = True
        for _ in range(5):
            d.retryTime = 0
            d.CheckStatus()
        self.assertEqual(Texts(), ["DFM 5 hasn't acknowledged its linkage (3 tries over 0 s). Still trying."])
        d.MP.failing.clear()
        d.retryTime = 0
        d.CheckStatus()
        self.assertEqual(len(Texts()), 2)
        self.assertIn("acknowledged its linkage", Texts()[-1])

    def test_instruction_sent_again_when_records_show_another(self):
        d = MakeDFM()
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 2, 1)
        d.CheckStatus()
        acked = d.ackedInstructionNumber
        self.assertEqual(acked, d.instructionNumber)
        # Too soon after the ACK, or a full reply (older records): no conclusion.
        d.ProcessPackets(Running(d, 7, readAfterAck=0.1), True)
        d.ProcessPackets(Running(d, 7, full=True), True)
        self.assertEqual(len(Sent(d)), 1)
        d.ProcessPackets(Running(d, acked), True)
        self.assertEqual(len(Sent(d)), 1)
        d.ProcessPackets(Running(d, 7), True)
        self.assertEqual(len(Sent(d)), 2)
        self.assertEqual(Texts()[-1], "DFM 5 is running instruction 7, not {} (Interval 3, Cycle 1). Sending it again.".format(acked))
        for _ in range(5):
            d.ProcessPackets(Running(d, 7), True)
        self.assertEqual(len(Sent(d)), 1 + DFM.MAX_INSTRUCTION_RESENDS)
        self.assertEqual(len([t for t in Texts() if "Not sending it again" in t]), 1)


def Note(text, seconds=0, kind=Enums.MESSAGETYPE.NOTICE, dfmID=5):
    return Message.Message(dfmID, datetime.datetime(2026, 1, 1) + datetime.timedelta(seconds=seconds), 0, text, kind, -99)


class Messages(unittest.TestCase):
    def setUp(self):
        MESSAGES.clear()

    def test_repeats_counted_on_one_line_per_10_minutes(self):
        messages = MessagesList.MessageList()
        for t in range(0, 900, 4):                    # a DFM not answering, every read
            messages.AddMessage(Note("No answer", t))
        messages.AddMessage(Note("No answer", 8, dfmID=6))
        self.assertEqual([(m.DFMId, m.repeatCount) for m in messages.theMessages], [(5, 149), (5, 74), (6, 0)])
        self.assertEqual(messages.theMessages[0].Text(), "No answer (repeated 149 more times, the last at 00:09:56)")

    def test_errors_kept_notices_capped(self):
        messages = MessagesList.MessageList()
        messages.maxNotices = 3
        for i in range(5):
            messages.AddMessage(Note("Notice {}".format(i)))
            messages.AddMessage(Note("Error {}".format(i), kind=Enums.MESSAGETYPE.ERROR))
        self.assertEqual(len([m for m in messages.theMessages if m.messageType == Enums.MESSAGETYPE.ERROR]), 5)
        self.assertEqual(len(messages), 8)
        self.assertIn("2 more notices were not kept, after the first 3", messages.GetMessageStringForFile())

    def test_screen_shows_the_most_recent_errors(self):
        messages = MessagesList.MessageList()
        for i in range(150):
            messages.AddMessage(Note("Error {}".format(i), i, Enums.MESSAGETYPE.ERROR))
        shown = str(messages).splitlines()
        self.assertEqual(shown[0], "The 100 most recent of 150 messages. All are in Messages.csv.")
        self.assertIn("Error 50 ", shown[1])
        self.assertIn("Error 149 ", shown[-1])

    def test_file_quotes_commas(self):
        messages = MessagesList.MessageList()
        messages.AddMessage(Note("Data file write failed: disk full, read-only", kind=Enums.MESSAGETYPE.ERROR))
        rows = list(csv.reader(io.StringIO(messages.GetMessageStringForFile())))
        self.assertEqual(rows[0], MessagesList.FILE_HEADER)
        self.assertEqual(rows[1][5:], ["Data file write failed: disk full, read-only", "Error"])

    def test_repeated_and_lost_records(self):
        d = MakeDFM()
        d.ProcessPackets(V4Packets(d, range(1, 11)), True)
        d.ProcessPackets(V4Packets(d, range(5, 13)), True)     # ACK missed: 5-10 again
        d.ProcessPackets(V4Packets(d, range(16, 18)), True)    # 13-15 never came
        self.assertEqual(Texts(), ["Records Index 5 to 10 were sent again after a missed ACK; they were already saved.",
                                   "Lost 3 records (0.6 s): Index 13 to 15, from 00:00:02."])
        self.assertEqual([m.messageType for m in MESSAGES], [Enums.MESSAGETYPE.NOTICE, Enums.MESSAGETYPE.ERROR])

    def test_error_bits_named_once_each_time_they_appear(self):
        d = MakeProbedDFM(b"3.5.0")
        MESSAGES.clear()
        for index, flags in enumerate([0, 0x02, 0x02, 0x42, 0x00, 0x40], start=1):
            d.UpdateReportedValues([Packet56(errorFlags=flags, index=index)], True)
        texts = Texts()
        self.assertEqual(len(texts), 3)
        self.assertIn("record buffer overflowed", texts[0])
        self.assertEqual(MESSAGES[0].messageType, Enums.MESSAGETYPE.ERROR)
        self.assertEqual(texts[1], "DFM 5 error: AI Int (New ADC readings arrived before the last ones were used)")
        self.assertEqual(texts[2], texts[1])
        self.assertEqual(MESSAGES[1].messageType, Enums.MESSAGETYPE.NOTICE)


class Writing(unittest.TestCase):
    def test_records_written_every_10_s(self):
        group = object.__new__(DFMGroup.DFMGroup)
        d = MakeDFM()
        d.ProcessPackets(V4Packets(d, range(1, 4)), True)
        f = io.StringIO()
        group.theDFMs, group.currentDFMKeysList, group.currentDFMIndex = {5: d}, [5], 0
        group.theFiles, group.writeFailedIDs = {5: f}, set()
        group.writeStartTimes = {5: datetime.datetime.today()}
        group.nextWriteTimes = {5: time.monotonic() + 5}
        group.theMessageList = MessagesList.MessageList()
        group.messagesWrittenAt = group.theMessageList.changeCount   # nothing new to write
        group.WriteStep()
        self.assertEqual(f.getvalue(), "")
        group.nextWriteTimes[5] = time.monotonic() - 1
        group.WriteStep()
        self.assertEqual(len(f.getvalue().splitlines()), 3)
        self.assertGreater(group.nextWriteTimes[5], time.monotonic() + 9)


class Compatibility(unittest.TestCase):
    OLD_BOARD_PROGRAM = ("[Paradigm NF]\nType: NonFeeding\nOnDelayMs: 500\n"
                         "[Paradigm Hold]\nType: ClosedLoop\nHoldMs: 70000\n"
                         "[Paradigm CL]\nType: ClosedLoop\nHoldMs: 500\n"
                         "[DFM]\nID: 2\nInterval: NF, Lit, {w}, 10\nInterval: Hold, Lit, {w}, 10\n"
                         "[DFM]\nID: 3\nInterval: CL, Lit, {w}, 10\n").format(w=WELLS)

    def Problems(self, version):
        group = object.__new__(DFMGroup.DFMGroup)
        group.theDFMs = {5: MakeDFM(version), 2: MakeDFM(version)}
        group.theDFMs[2].ID = 2
        group.currentProgram = Program.MCUProgram()
        with open(os.path.join(support.ROOT, "FLICPrograms", "ParadigmExamples.txt"), encoding="utf-8-sig") as f:
            self.assertTrue(group.currentProgram.LoadProgram(f.readlines(), group.theDFMs))
        return group.CheckProgramCompatibility()

    def ProblemsWithProbedDFMs(self, *dfms):
        group = object.__new__(DFMGroup.DFMGroup)
        group.theDFMs = {d.ID: d for d in dfms}
        group.currentProgram = Program.MCUProgram()
        self.assertTrue(group.currentProgram.LoadProgram(self.OLD_BOARD_PROGRAM.splitlines(keepends=True), group.theDFMs),
                        group.currentProgram.loadError)
        return group.CheckProgramCompatibility()

    def test_old_firmware_refused(self):
        problems = self.Problems("3.5.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("DFM 5", problems[0])
        self.assertIn("4.0.0", problems[0])
        self.assertEqual(self.Problems("4.0.0"), [])

    def test_1_0_5_board_listed_with_each_reason(self):
        problems = self.ProblemsWithProbedDFMs(MakeProbedDFM(COMM.LEGACY_VERSION, ID=2), MakeProbedDFM(COMM.LEGACY_VERSION, ID=3))
        self.assertEqual(len(problems), 1)   # DFM 3 runs a plain closed loop
        for words in ("DFM 2", "1.0.5", "NonFeeding", "65535", "2.0.0"):
            self.assertIn(words, problems[0])
        self.assertEqual(self.ProblemsWithProbedDFMs(MakeProbedDFM(b"2.0.1", ID=2), MakeProbedDFM(COMM.LEGACY_VERSION, ID=3)), [])
        self.assertEqual(self.ProblemsWithProbedDFMs(MakeProbedDFM(b"4.0.0", ID=2)), [])


if __name__ == "__main__":
    unittest.main()
