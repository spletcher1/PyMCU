"""DFM bookkeeping: instruction numbers, keeping Paradigm state, Activation totals, what each
firmware generation is sent, and the checks before a Program starts."""
import support  # noqa: F401  (must come first)

import datetime
import os
import unittest

import COMM
import DFM
import DFMErrors
import DFMGroup
import Enums
import Instruction
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
