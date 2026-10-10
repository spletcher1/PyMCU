"""DFM bookkeeping: instruction numbers, keeping Paradigm state, Activation totals and checks
before a Program starts."""
import support  # noqa: F401  (must come first)

import datetime
import os
import unittest

import DFM
import DFMGroup
import Enums
import Instruction
import Program
from test_protocol import PR10, Record

import StatusPacket


class FakeMP:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def Call(*args):
            self.calls.append((name,) + args)
            return True
        return Call


def MakeDFM(version="4.0.0"):
    d = DFM.DFM(5, Enums.DFMTYPE.PLETCHERV3, FakeMP())
    d.firmwareVersion = version
    d.DFMSubType = Enums.DFMSUBTYPE.V2
    d.isVersionGetNeeded = False
    d.status = Enums.CURRENTSTATUS.RECORDING
    return d


def Sent(d):
    return [c for c in d.MP.calls if c[0].startswith("SendInstruction") or c[0] == "SendParadigmInstruction"]


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
        messages = []
        DFM.DFM.DFM_message += messages.append
        d.UpdateInstruction(Instruction.DFMInstruction(Enums.DARKSTATE.ON, PR10()), False, 1, 1)
        d.CheckStatusV3()
        self.assertEqual(len(Sent(d)), 1)
        self.assertTrue(any("can't run" in m.message for m in messages))


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


class Compatibility(unittest.TestCase):
    def Problems(self, version):
        group = object.__new__(DFMGroup.DFMGroup)
        group.theDFMs = {5: MakeDFM(version), 2: MakeDFM(version)}
        group.theDFMs[2].ID = 2
        group.currentProgram = Program.MCUProgram()
        with open(os.path.join(support.ROOT, "FLICPrograms", "ParadigmExamples.txt"), encoding="utf-8-sig") as f:
            self.assertTrue(group.currentProgram.LoadProgram(f.readlines(), group.theDFMs))
        return group.CheckProgramCompatibility()

    def test_old_firmware_refused(self):
        problems = self.Problems("3.5.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("DFM 5", problems[0])
        self.assertIn("4.0.0", problems[0])
        self.assertEqual(self.Problems("4.0.0"), [])


if __name__ == "__main__":
    unittest.main()
