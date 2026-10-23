"""DFM bookkeeping per firmware generation: which instruction format goes out, which error labels
show, what happens with settings or firmware a board can't take, and how records are read."""
import support  # noqa: F401  (must come first)

import datetime
import unittest

import COMM
import DFM
import DFMErrors
import Enums
import Instruction
import StatusPacket
from test_protocol import ClosedLoop, Record

MESSAGES = []
DFM.DFM.DFM_message += MESSAGES.append


class FakeMP:
    """Stands in for DataGetter: records every call and answers the version it was given."""
    def __init__(self, version):
        self.version = version
        self.calls = []

    def GetVersion(self, ID):
        self.calls.append(("GetVersion", ID))
        return self.version

    def __getattr__(self, name):
        def Call(*args):
            self.calls.append((name,) + args)
            return True
        return Call


def MakeDFM(version=b"2.0.1", ID=5):
    d = DFM.DFM(ID, Enums.DFMTYPE.PLETCHERV3, FakeMP(version))
    d.ReadFirmwareVersion()
    d.status = Enums.CURRENTSTATUS.RECORDING
    return d


def Sent(d):
    return [c for c in d.MP.calls if c[0].startswith("SendInstruction")]


def MessagesAbout(dfmID, words):
    return [m for m in MESSAGES if m.DFMId == dfmID and words in m.message]


def Packet(errorFlags=0, index=1, training=()):
    sp = StatusPacket.StatusPacket(0, 5, Enums.DFMTYPE.PLETCHERV3)
    sp.ProcessStatusPacket(Record(index=index, errorFlags=errorFlags, training=training), datetime.datetime(2026, 1, 1), 0)
    return sp


class Generations(unittest.TestCase):
    def test_1_0_5_board(self):
        d = MakeDFM(COMM.LEGACY_VERSION)
        self.assertEqual(d.firmwareVersion, "1.0.5")
        self.assertEqual(d.DFMSubType, Enums.DFMSUBTYPE.V1_0_5)
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY_BEFORE_3_5_0)
        d.UpdateInstruction(ClosedLoop(), False)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV1_0_5"])

    def test_2_0_1_board(self):
        d = MakeDFM(b"2.0.1")
        self.assertEqual(d.DFMSubType, Enums.DFMSUBTYPE.V2)
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY_BEFORE_3_5_0)
        d.UpdateInstruction(ClosedLoop(), False)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV2_0"])

    def test_3_5_0_board(self):
        d = MakeDFM(b"3.5.0")
        self.assertEqual(d.DFMSubType, Enums.DFMSUBTYPE.V2)
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY)
        self.assertTrue(d.isSupported)

    def test_4_0_0_board_is_left_alone(self):
        MESSAGES.clear()
        d = MakeDFM(b"4.0.0")
        self.assertFalse(d.isSupported)
        self.assertEqual(d.firmwareVersion, "4.0.0")
        d.UpdateInstruction(ClosedLoop(), False)
        d.CheckStatusV3()
        self.assertEqual(Sent(d), [])
        d.ReadFirmwareVersion()   # said once, not on every probe
        said = MessagesAbout(5, "PyMCU 4.0.0")
        self.assertEqual(len(said), 1)
        self.assertEqual(said[0].messageType, Enums.MESSAGETYPE.ERROR)
        self.assertIn("firmware 4.0.0", said[0].message)

    def test_1_0_5_board_refuses_2_0_0_settings(self):
        MESSAGES.clear()
        d = MakeDFM(COMM.LEGACY_VERSION)
        nonFeeding = Instruction.DFMInstruction(Enums.DARKSTATE.OFF, 40, 32776, 1000, 500, 0)
        d.UpdateInstruction(nonFeeding, False)
        d.CheckStatusV3()
        self.assertEqual(Sent(d), [])
        refusals = MessagesAbout(5, "can't run")
        self.assertEqual(len(refusals), 1)
        self.assertIn("non-feeding", refusals[0].message)
        self.assertEqual(refusals[0].messageType, Enums.MESSAGETYPE.ERROR)
        d.CheckStatusV3()                     # not repeated on the next pass
        self.assertEqual(len(MessagesAbout(5, "can't run")), 1)
        d.UpdateInstruction(ClosedLoop(), False)
        d.CheckStatusV3()                     # a plain Interval still goes out
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV1_0_5"])


class Records(unittest.TestCase):
    def test_probe_error_masked_once_on_1_0_5(self):
        d = MakeDFM(COMM.LEGACY_VERSION)
        d.UpdateReportedValues([Packet(errorFlags=0x04, index=1)], False)
        self.assertEqual(d.currentDFMErrors.GetStatus((2,)), Enums.REPORTEDERRORSTATUS.NEVER)
        d.UpdateReportedValues([Packet(errorFlags=0x04, index=2)], False)   # a real one shows
        self.assertEqual(d.currentDFMErrors.GetStatus((2,)), Enums.REPORTEDERRORSTATUS.CURRENT)
        d.ReadFirmwareVersion()                                            # each probe sets it again
        self.assertTrue(d.maskProbeError)
        d = MakeDFM(b"2.0.1")                 # a board that answered wasn't asked anything it can't take
        d.UpdateReportedValues([Packet(errorFlags=0x04)], False)
        self.assertEqual(d.currentDFMErrors.GetStatus((2,)), Enums.REPORTEDERRORSTATUS.CURRENT)

    def test_baseline_ignores_training_flag(self):
        d = MakeDFM(b"2.0.1")
        d.BaselineDFM()
        for index in range(1, 4):
            d.ProcessPackets([Packet(index=index, training=(0,))], False)
        self.assertEqual(list(d.signalBaselines[:2]), [100, 101])
        self.assertEqual(list(d.GetLastAnalogData(True)[:2]), [0, 0])
        self.assertEqual(d.GetLastAnalogData(False)[0], 100 + 65536)   # the data file keeps the flag


if __name__ == "__main__":
    unittest.main()
