"""DFM bookkeeping per firmware generation: which instruction format goes out, which error labels
show, and what happens with settings or firmware a board can't take."""
import support  # noqa: F401  (must come first)

import unittest

import COMM
import DFM
import DFMErrors
import Enums
import Instruction
from test_protocol import ClosedLoop

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


class Generations(unittest.TestCase):
    def test_1_0_5_board(self):
        d = MakeDFM(COMM.LEGACY_VERSION)
        self.assertEqual(d.firmwareVersion, "1.0.5")
        self.assertEqual(d.DFMSubType, Enums.DFMSUBTYPE.V1_5)
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY_BEFORE_2_0_2)
        d.UpdateInstruction(ClosedLoop(), False)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV1_5"])

    def test_2_0_1_board(self):
        d = MakeDFM(b"2.0.1")
        self.assertEqual(d.DFMSubType, Enums.DFMSUBTYPE.V2)
        self.assertIs(d.currentDFMErrors.display, DFMErrors.V3_ERROR_DISPLAY_BEFORE_2_0_2)
        d.UpdateInstruction(ClosedLoop(), False)
        d.CheckStatusV3()
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV2_0"])

    def test_3_5_0_board(self):
        d = MakeDFM(b"3.5.0")
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
        self.assertEqual([c[0] for c in Sent(d)], ["SendInstructionDFMV1_5"])


if __name__ == "__main__":
    unittest.main()
