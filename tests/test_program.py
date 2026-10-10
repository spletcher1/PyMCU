"""Program loading: [Paradigm] sections, new and old Interval lines, errors and Interval timing."""
import support  # noqa: F401  (must come first)

import datetime
import os
import unittest

import Enums
import Instruction
import Paradigm
import Program

PROGRAMS = os.path.join(support.ROOT, "FLICPrograms")


def Load(text):
    program = Program.MCUProgram()
    ok = program.LoadProgram(text.strip().splitlines(keepends=True), None)
    return program, ok


def LoadFile(name):
    with open(os.path.join(PROGRAMS, name), encoding="utf-8-sig") as f:
        program = Program.MCUProgram()
        return program, program.LoadProgram(f.readlines(), None)


WELLS = "20,Off,20,Off,20,Off,20,Off,20,Off,20,Off"


class NewFormat(unittest.TestCase):
    def test_example_file(self):
        program, ok = LoadFile("ParadigmExamples.txt")
        self.assertTrue(ok, program.loadError)
        self.assertEqual(len(program.theParadigms), 6)
        dfm5 = program.theInstructionSets[5]
        self.assertEqual([i.paradigm.name for i in dfm5.instructions], ["Closed", "PR10"])
        self.assertEqual(dfm5.instructions[1].elapsedStart, datetime.timedelta(minutes=30))
        self.assertEqual(list(dfm5.instructions[0].optoValues[:2]), [20, Instruction.OFF])
        self.assertEqual(program.theInstructionSets[1].instructions[0].optoValues[0], Instruction.ON)
        self.assertEqual(dfm5.instructions[0].theDarkState, Enums.DARKSTATE.ON)

    def test_defaults(self):
        program, ok = Load("""
[Paradigm A]
Type: ProgressiveRatio
ActivationMs: 500
Step: 10
[Paradigm B]
Type: ProgressiveRatio
ActivationMs: 500
Series: exponential
[DFM]
ID: 1
Interval: A, Lit, {}, 10
""".format(WELLS))
        self.assertTrue(ok, program.loadError)
        a, b = program.theParadigms["a"], program.theParadigms["b"]
        self.assertEqual((a.frequency, a.pulseWidth, a.eventGapMs, a.acclimation), (40, 8, 100, 0))
        self.assertEqual(a.SettingsWords(), [500, 0, 1, 10, 65535])
        self.assertEqual(b.SettingsWords(), [500, 1, 5000, 200, 65535])

    def ExpectError(self, text, line, fragment):
        program, ok = Load(text)
        self.assertFalse(ok)
        self.assertIn("Line {}:".format(line), program.loadError)
        self.assertIn(fragment, program.loadError)
        self.assertFalse(program.isProgramLoaded)

    def test_errors(self):
        self.ExpectError("[Paradigm A]\nType: ClosedLoop\nHoldMs: 5\nStep: 3", 4, "ClosedLoop Paradigms don't use Step")
        self.ExpectError("[Paradigm A]\nType: ClosedLoop\nColour: red", 3, "Unknown setting 'Colour'")
        self.ExpectError("[Paradigm A]\nType: FixedRatio\nActivationMs: 5", 1, "needs Ratio")
        self.ExpectError("[Paradigm A]\nType: ProgressiveRatio\nActivationMs: 5\nStep: 1\nScale: 3", 5,
                         "Scale is only for the Exponential Series")
        self.ExpectError("[Paradigm A]\nType: ClosedLoop\nFrequency: 100\nPulseWidth: 10", 4, "shorter than one period")
        self.ExpectError("[Paradigm A]\nType: Sometimes", 2, "Unknown Type 'Sometimes'")
        self.ExpectError("[Paradigm Off]\nType: OpenLoop", 1, "can't be a Paradigm name")
        self.ExpectError("[Paradigm A]\nType: OpenLoop\n[Paradigm a]\nType: OpenLoop", 3, "defined twice")
        self.ExpectError("[DFM]\nID: 1\nInterval: Missing, Lit, {}, 10".format(WELLS), 3, "No Paradigm named 'Missing'")
        self.ExpectError("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: 1\nInterval: A, Lit, 20, 10", 5, "15 expected")
        self.ExpectError("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: 1\nInterval: A, Lit, 0,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 10",
                         5, "On, Off or a signal level")
        self.ExpectError("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: 1\nInterval: A, Bright, {}, 10".format(WELLS), 5, "Dark or Lit")
        self.ExpectError("[General]\nExpDurationMin: 10\nOptoLid: Six", 3, "Unknown [General] setting 'OptoLid'")
        self.ExpectError("[Genral]", 1, "Unknown section [Genral]")
        self.ExpectError("[DFM]\nProgramType: Linear", 2, "must start with its ID")
        self.ExpectError("Interval: 1", 1, "Expected a section")

    def test_start_time_without_seconds(self):
        program, ok = Load("[General]\nStartTime: 13:45")
        self.assertTrue(ok, program.loadError)
        self.assertEqual((program.startTime.hour, program.startTime.minute), (13, 45))


class OldFormat(unittest.TestCase):
    def test_existing_programs_load(self):
        for name in ("TestProgram1.txt", "TestProgram2.txt", "OptoLidOutputTest.txt"):
            program, ok = LoadFile(name)
            self.assertTrue(ok, "{}: {}".format(name, program.loadError))

    def Paradigm(self, general, interval="0,20,20,20,20,20,20,20,20,20,20,20,20,10"):
        program, ok = Load("[General]\n{}\n[DFM]\nID: 1\nInterval: {}".format(general, interval))
        self.assertTrue(ok, program.loadError)
        return program.theInstructionSets[1].instructions[0].paradigm

    def test_translation(self):
        p = self.Paradigm("OptoDecay: 500\nMaxTimeOn: 2500")
        self.assertEqual((p.type, p.Get("HoldMs"), p.Get("MaxOnMs")), (Paradigm.ParadigmType.CLOSEDLOOP, 500, 2500))
        p = self.Paradigm("OptoDelay: 60000\nOptoDecay: 1000")
        self.assertEqual((p.type, p.Get("ActivationMs"), p.Get("LockoutMs")), (Paradigm.ParadigmType.FIXEDINTERVAL, 1000, 60000))
        p = self.Paradigm("OptoPW: 32776\nOptoDelay: 500\nOptoDecay: 21600000")
        self.assertEqual((p.type, p.pulseWidth, p.Get("OnDelayMs"), p.Get("MaxOnMs")),
                         (Paradigm.ParadigmType.NONFEEDING, 8, 500, 21600000))
        p = self.Paradigm("MaxTimeOn: -1")
        self.assertEqual(p.Get("MaxOnMs"), 0)
        # Equal old settings make the same Paradigm, so Paradigm state carries over.
        program, ok = Load("[General]\nOptoDecay: 500\n[DFM]\nID: 1\nInterval: 0,20,20,20,20,20,20,20,20,20,20,20,20,10\n"
                           "Interval: 1,30,30,30,30,30,30,30,30,30,30,30,30,10")
        names = [i.paradigm.name for i in program.theInstructionSets[1].instructions]
        self.assertEqual(names[0], names[1])
        self.assertEqual(names[0], "ClosedLoop-40Hz-8ms-Hold500-MaxOn0")

    def test_19_values(self):
        p = self.Paradigm("", "0,20,-1,20,-1,20,-1,20,-1,20,-1,20,-1,40,8,1000,0,0,10")
        self.assertEqual((p.type, p.Get("HoldMs")), (Paradigm.ParadigmType.CLOSEDLOOP, 1000))

    def test_refused(self):
        program, ok = Load("[DFM]\nID: 1\nInterval: 0,20,-1,20,-1,20,-1,20,-1,20,-1,20,-1,40,8,500,1000,1000000000,30")
        self.assertFalse(ok)
        self.assertIn("Line 3:", program.loadError)
        self.assertIn("progressive ratio", program.loadError)
        program, ok = Load("[DFM]\nID: 1\nInterval: 0,20,-1,20,-1,20,-1,20,-1,20,-1,20,-1,5160,8,500,1000,1000000000,360")
        self.assertFalse(ok)
        self.assertIn("acclimation", program.loadError)


class Timing(unittest.TestCase):
    def Position(self, programType, minutes, intervals="10,10"):
        lines = ["[Paradigm A]", "Type: OpenLoop", "[DFM]", "ID: 1", "ProgramType: " + programType]
        lines += ["Interval: A, Lit, {}, {}".format(WELLS, m) for m in intervals.split(",")]
        program, ok = Load("\n".join(lines))
        self.assertTrue(ok, program.loadError)
        iset = program.theInstructionSets[1]
        start = datetime.datetime(2026, 1, 1, 12, 0, 0)
        _, index, cycle = iset.GetPosition(start + datetime.timedelta(minutes=minutes), start)
        return index, cycle

    def test_positions(self):
        self.assertEqual(self.Position("Linear", 15), (1, 1))
        self.assertEqual(self.Position("Linear", 95), (1, 1))
        self.assertEqual(self.Position("Repeating", 25), (0, 2))
        self.assertEqual(self.Position("Repeating", 15), (1, 1))
        self.assertEqual(self.Position("Constant", 15), (0, 1))
        self.assertEqual(self.Position("Linear", -5), (None, None))

    def test_circadian_must_add_up(self):
        program, ok = Load("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: 1\nProgramType: Circadian\n"
                           "Interval: A, Lit, {}, 600".format(WELLS))
        self.assertFalse(ok)
        self.assertIn("1440", program.loadError)

    def test_firmware_needed(self):
        program, ok = LoadFile("ParadigmExamples.txt")
        self.assertEqual(program.FirmwareNeeded(2), [])
        self.assertEqual(program.FirmwareNeeded(5), ["the ProgressiveRatio Paradigm type"])
        self.assertEqual(program.FirmwareNeeded(6), ["the FixedRatio Paradigm type"])


if __name__ == "__main__":
    unittest.main()
