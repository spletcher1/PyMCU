"""Program loading: [Paradigm] sections, new and old Interval lines, errors and Interval timing."""
import support  # noqa: F401  (must come first)

import datetime
import os
import types
import unittest

import DFMGroup
import Enums
import Instruction
import Paradigm
import Program
from test_dfm import FakeMP, MakeDFM

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
    def test_shipped_programs_load(self):
        names = sorted(n for n in os.listdir(PROGRAMS) if n.endswith(".txt"))
        self.assertIn("OptoLidOutputTest.txt", names)
        self.assertIn("OptoTest6_TrainingFirst.txt", names)
        for name in names:
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
        self.assertEqual(program.FirmwareNeeded(5), ["the ProgressiveRatio Paradigm type needs firmware 4.0.0"])
        self.assertEqual(program.FirmwareNeeded(6), ["the FixedRatio Paradigm type needs firmware 4.0.0"])
        # Firmware 1.0.5 also can't take NonFeeding or times above 65535 ms; 2.0.1 can.
        program, ok = Load("[Paradigm NF]\nType: NonFeeding\nOnDelayMs: 500\n[DFM]\nID: 1\nInterval: NF, Lit, {}, 10".format(WELLS))
        self.assertTrue(ok, program.loadError)
        self.assertEqual(program.FirmwareNeeded(1), [])
        self.assertEqual(program.FirmwareNeeded(1, (2, 0, 1)), [])
        self.assertEqual(program.FirmwareNeeded(1, (1, 0, 5)), ["the NonFeeding Paradigm type needs firmware 2.0.0"])


class WholeMinutes(unittest.TestCase):
    def test_simple_program_starts_on_the_minute(self):
        # The GUI asks for now + 1 minute, seconds and all; the program must not keep them.
        program = Program.MCUProgram()
        program.CreateSimpleProgram(datetime.datetime(2026, 10, 14, 23, 42, 18, 500), datetime.timedelta(minutes=180))
        self.assertEqual(program.startTime, datetime.datetime(2026, 10, 14, 23, 42))
        self.assertEqual(program.GetEndTime(), datetime.datetime(2026, 10, 15, 2, 42))

    def test_next_minute_is_the_top_of_the_coming_minute(self):
        before = datetime.datetime.today()
        start = Program.NextMinute()
        self.assertEqual((start.second, start.microsecond), (0, 0))
        self.assertTrue(before < start <= before + datetime.timedelta(minutes=1))


class AllSection(unittest.TestCase):
    """A [DFM] section with 'ID: All' covers the connected DFMs the file doesn't list."""
    @staticmethod
    def Devices(*ids):
        return {i: types.SimpleNamespace(ID=i, DFMType=Enums.DFMTYPE.ENVMONV3 if i == 99 else Enums.DFMTYPE.PLETCHERV3)
                for i in ids}

    def test_id_all_covers_dfms_not_listed(self):
        text = ("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: All\nInterval: A, Lit, {w}, 10\n"
                "[DFM]\nID: 2\nInterval: A, Dark, {w}, 10\n").format(w=WELLS)
        program = Program.MCUProgram()
        self.assertTrue(program.LoadProgram(text.splitlines(keepends=True), self.Devices(2, 3, 4, 99)), program.loadError)
        sets = program.theInstructionSets
        self.assertEqual(sorted(sets), [2, 3, 4, 99])
        self.assertEqual(sets[2].instructions[0].theDarkState, Enums.DARKSTATE.ON)     # its own section wins
        self.assertEqual(sets[3].instructions[0].theDarkState, Enums.DARKSTATE.OFF)
        self.assertEqual(sets[3].instructions[0].optoValues[0], 20)
        self.assertEqual(sets[99].instructions[0].optoValues[0], Instruction.OFF)      # not the monitor
        # Each DFM's baseline goes into its own Intervals.
        self.assertIsNot(sets[3].instructions[0], sets[4].instructions[0])
        # Without a list of DFMs (the tests' usual call) the section is simply kept aside.
        program, ok = Load(text)
        self.assertTrue(ok, program.loadError)
        self.assertEqual(sorted(program.theInstructionSets), [2])

    def test_id_all_only_once(self):
        program, ok = Load("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: All\n[DFM]\nID: All")
        self.assertFalse(ok)
        self.assertIn("Line 6:", program.loadError)
        self.assertIn("Only one [DFM] section can have ID: All", program.loadError)


class StagedProgram(unittest.TestCase):
    """A staged program reads only the DFM on screen and doesn't baseline until it starts."""
    def Group(self):
        group = object.__new__(DFMGroup.DFMGroup)
        group.MP = FakeMP()
        group.theDFMs = {2: MakeDFM(), 3: MakeDFM()}
        group.theDFMs[2].ID = 2
        group.theDFMs[3].ID = 3
        group.activeDFM = group.theDFMs[2]
        group.isReadWorkerRunning = False
        group.isStagedFocused = False
        group.programReadInterval = ""
        group.currentProgram = Program.MCUProgram()
        group.currentProgram.CreateSimpleProgram(Program.NextMinute(), datetime.timedelta(minutes=10))
        group.StopReadWorker = group.StartProgramWorker = lambda: None
        return group

    def Focus(self, group):
        return [c[1] for c in group.MP.calls if c[0] == "SetFocusDFM"]

    def test_staging_reads_the_dfm_on_screen_and_does_not_baseline(self):
        group = self.Group()
        group.StageCurrentProgram()
        self.assertEqual(self.Focus(group), [2])
        self.assertFalse(any(d.isCalculatingBaseline for d in group.theDFMs.values()))
        group.SetActiveDFM(3)
        self.assertEqual(self.Focus(group), [2, 3])

    def test_instructions_wait_for_each_baseline(self):
        group = self.Group()
        group.currentProgram.startTime = datetime.datetime.today() - datetime.timedelta(minutes=1)
        group.theDFMs[3].BaselineDFM()
        group.UpdateDFMInstructions()
        self.assertTrue(group.theDFMs[2].isInstructionUpdateNeeded)
        self.assertFalse(group.theDFMs[3].isInstructionUpdateNeeded)


if __name__ == "__main__":
    unittest.main()
