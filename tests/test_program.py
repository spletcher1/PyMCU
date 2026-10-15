"""Program files: what loads, what is refused with its line number, and the compatibility check
against the connected DFMs' firmware."""
import support  # noqa: F401  (must come first)

import datetime
import os
import types
import unittest

import COMM
import DFMGroup
import Enums
import Program
from test_dfm import FakeMP, MakeDFM

GENERAL = """[General]
ExpDurationMin: 60
OptoFrequency: 40
OptoPW: 8
OptoDelay: 0
OptoDecay: 0
MaxTimeOn: 0
Linkage: 1,2,3,4,5,6,7,8,9,10,11,12
Baseline: Yes
"""
DFM2 = "[DFM]\nID: 2\n"   # lines 10 and 11 after GENERAL; the first Interval is line 12

NOTICES = []
Program.MCUProgram.Program_message += NOTICES.append


def Load(text, *dfms):
    program = Program.MCUProgram()
    ok = program.LoadProgram(text.splitlines(keepends=True), {d.ID: d for d in dfms})
    return ok, program


class Loading(unittest.TestCase):
    def test_14_and_19_number_intervals(self):
        text = GENERAL + DFM2 + ("ProgramType: Repeating\n"
                                 "Interval: 1,0,0,0,0,0,0,0,0,0,0,0,0,10\n"
                                 "Interval: 0,20,30,9999,-1,0,0,0,0,0,0,0,0,40,12,1000,0,0,30\n")
        ok, program = Load(text, MakeDFM(ID=2), MakeDFM(ID=5))
        self.assertTrue(ok)
        self.assertTrue(program.isProgramLoaded)
        self.assertEqual(sorted(program.theInstructionSets), [2, 5])
        first, second = program.theInstructionSets[2].instructions
        self.assertEqual((first.theDarkState, first.frequency, first.pulseWidth, first.duration),
                         (Enums.DARKSTATE.ON, 40, 8, datetime.timedelta(minutes=10)))
        self.assertEqual(list(second.optoValues[:5]), [20, 30, -1, -1, 0])
        self.assertEqual((second.frequency, second.pulseWidth, second.decay, second.delay, second.maxTimeOn),
                         (40, 12, 1000, 0, 0))
        self.assertEqual((second.elapsedStart, second.duration), (datetime.timedelta(minutes=10), datetime.timedelta(minutes=30)))
        # DFM 5 isn't in the file, so it gets a simple program from the [General] settings.
        simple = program.theInstructionSets[5].instructions
        self.assertEqual(len(simple), 1)
        self.assertEqual((simple[0].frequency, simple[0].duration), (40, datetime.timedelta(minutes=60)))
        self.assertTrue(any("DFM 5 not listed" in n.message for n in NOTICES))

    def test_2_0_0_forms_and_long_times_load(self):
        text = (GENERAL.replace("OptoFrequency: 40", "OptoFrequency: 1576") + DFM2
                + "Interval: 0,0,0,0,0,0,0,0,0,0,0,0,0,40,32776,1000,5000,20000,30\n"
                + "Interval: 0,0,0,0,0,0,0,0,0,0,0,0,0,40,8,70000,0,0,30\n")
        ok, program = Load(text, MakeDFM(ID=2))
        self.assertTrue(ok, program.loadError)
        self.assertEqual(program.optoFrequency, 1576)
        self.assertEqual(program.theInstructionSets[2].instructions[0].pulseWidth, 32776)

    def test_start_time_forms(self):
        ok, program = Load(GENERAL + "StartTime: 10/14/2026 01:02:03\n", MakeDFM(ID=2))
        self.assertTrue(ok, program.loadError)
        self.assertEqual(program.startTime, datetime.datetime(2026, 10, 14, 1, 2, 3))
        ok, program = Load(GENERAL + "StartTime: 01:02:03\n", MakeDFM(ID=2))
        self.assertTrue(ok, program.loadError)
        self.assertEqual(program.startTime.time(), datetime.time(1, 2, 3))

    def Refusal(self, text, expected):
        NOTICES.clear()
        ok, program = Load(text, MakeDFM(ID=2))
        self.assertFalse(ok)
        self.assertFalse(program.isProgramLoaded)
        self.assertIn(expected, program.loadError)
        self.assertTrue(any(("Problem loading program: " + expected) in n.message for n in NOTICES))

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

    def test_id_all_covers_dfms_not_listed(self):
        text = GENERAL + "[DFM]\nID: All\nInterval: 0,50,50,50,50,50,50,50,50,50,50,50,50,10\n" + DFM2 + \
            "Interval: 0,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,10\n"
        envMon = types.SimpleNamespace(ID=99, DFMType=Enums.DFMTYPE.ENVMONV3)
        ok, program = Load(text, MakeDFM(ID=2), MakeDFM(ID=3), MakeDFM(ID=4), envMon)
        self.assertTrue(ok, program.loadError)
        sets = program.theInstructionSets
        self.assertEqual(sorted(sets), [2, 3, 4, 99])
        self.assertEqual(sets[2].instructions[0].optoValues[0], -1)     # its own section wins
        self.assertEqual(sets[3].instructions[0].optoValues[0], 50)
        self.assertEqual(sets[99].instructions[0].optoValues[0], -1)    # not the monitor
        # Each DFM's baseline goes into its own Intervals.
        self.assertIsNot(sets[3].instructions[0], sets[4].instructions[0])

    def test_shipped_programs_load(self):
        folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "FLICPrograms")
        for name in sorted(os.listdir(folder)):
            with open(os.path.join(folder, name), encoding="utf-8-sig") as f:
                ok, program = Load(f.read(), MakeDFM(ID=2))
            self.assertTrue(ok, name + ": " + program.loadError)

    def test_refusals_name_the_line(self):
        self.Refusal(GENERAL + DFM2 + "Interval: 1,0,0,0,0,0,0,0,0,0,0,0,0,10,5\n",
                     "line 12: an Interval needs 14 or 19 numbers, not 15")
        self.Refusal(GENERAL.replace("OptoPW: 8", "OptoPW: 0"), "line 4: OptoPW must be 1 to 1000 ms")
        self.Refusal(GENERAL.replace("OptoPW: 8", "OptoPW: abc"), "line 4: OptoPW must be a whole number, not 'abc'")
        self.Refusal(GENERAL.replace("OptoFrequency: 40", "OptoFrequency: 501"), "line 3: OptoFrequency must be 1 to 500 Hz")
        self.Refusal(GENERAL.replace("OptoFrequency: 40", "OptoFrequency: 1024"), "line 3: OptoFrequency must be 1 to 500 Hz")
        self.Refusal(GENERAL.replace("OptoDecay: 0", "OptoDecay: 4294967296"), "line 6: OptoDecay must be 0 to 4294967295")
        self.Refusal(GENERAL + DFM2 + "Interval: 2,0,0,0,0,0,0,0,0,0,0,0,0,10\n", "line 12: dark (the first number) must be 0 to 1")
        self.Refusal(GENERAL + DFM2 + "Interval: 0,0,0,0,0,0,0,0,0,0,0,0,0,40,32776,0,500,0,30\n",
                     "line 12: OptoPW 32776 is non-feeding activation, which needs OptoDecay above 0")
        self.Refusal(GENERAL + DFM2 + "Interval: 0,0,0,0,0,0,0,0,0,0,0,0,0,40,30,0,0,0,30\n",
                     "line 12: OptoPW 30 ms is not shorter than one period at 40 Hz (25.0 ms)")
        self.Refusal(GENERAL.replace("OptoPW: 8", "OptoPW: 30"), "General settings: OptoPW 30 ms is not shorter than one period")
        self.Refusal(GENERAL + "StartTime: noon\n", "line 10: StartTime must be")
        self.Refusal(GENERAL + DFM2 + "ProgramType: Circadian\nInterval: 0,0,0,0,0,0,0,0,0,0,0,0,0,600\n",
                     "DFM 2: a Circadian program's Intervals must add up to 24 hours, not 10")


class Compatibility(unittest.TestCase):
    NON_FEEDING = (GENERAL.replace("OptoPW: 8", "OptoPW: 32776").replace("OptoDecay: 0", "OptoDecay: 1000")
                   .replace("OptoDelay: 0", "OptoDelay: 500"))
    EACH_SETTING = GENERAL + DFM2 + ("Interval: 0,0,0,0,0,0,0,0,0,0,0,0,0,1576,8,1000,0,0,30\n"
                                     "Interval: 0,0,0,0,0,0,0,0,0,0,0,0,0,40,8,1000,5000,20000,30\n"
                                     "Interval: 0,0,0,0,0,0,0,0,0,0,0,0,0,40,8,70000,0,0,30\n")

    def Problems(self, text, *dfms):
        group = object.__new__(DFMGroup.DFMGroup)
        group.theDFMs = {d.ID: d for d in dfms}
        group.currentProgram = Program.MCUProgram()
        self.assertTrue(group.currentProgram.LoadProgram(text.splitlines(keepends=True), group.theDFMs),
                        group.currentProgram.loadError)
        return group.CheckProgramCompatibility()

    def test_1_0_5_board_is_listed_per_setting(self):
        problems = self.Problems(self.NON_FEEDING, MakeDFM(COMM.LEGACY_VERSION, ID=2), MakeDFM(b"2.0.1", ID=3))
        self.assertEqual(len(problems), 1)
        for words in ("DFM 2", "1.0.5", "non-feeding", "2.0.0"):
            self.assertIn(words, problems[0])
        self.assertEqual(self.Problems(self.NON_FEEDING, MakeDFM(b"2.0.1", ID=2)), [])
        problems = self.Problems(self.EACH_SETTING, MakeDFM(COMM.LEGACY_VERSION, ID=2))
        self.assertEqual(len(problems), 1)
        for words in ("training", "progressive ratio", "65535"):
            self.assertIn(words, problems[0])
        self.assertEqual(self.Problems(self.EACH_SETTING, MakeDFM(b"3.5.0", ID=2)), [])
        self.assertEqual(self.Problems(GENERAL, MakeDFM(COMM.LEGACY_VERSION, ID=2)), [])

    def test_4_0_0_board_is_listed(self):
        problems = self.Problems(GENERAL, MakeDFM(b"4.0.0", ID=2), MakeDFM(b"3.5.0", ID=3))
        self.assertEqual(len(problems), 1)
        self.assertIn("DFM 2", problems[0])
        self.assertIn("PyMCU 4.0.0", problems[0])


if __name__ == "__main__":
    unittest.main()



class StagedProgram(unittest.TestCase):
    """A staged program reads only the DFM on screen and doesn't baseline until it starts."""
    def Group(self):
        group = object.__new__(DFMGroup.DFMGroup)
        group.MP = FakeMP(b"2.0.1")
        group.theDFMs = {2: MakeDFM(ID=2), 3: MakeDFM(ID=3)}
        group.activeDFM = group.theDFMs[2]
        group.isReadWorkerRunning = False
        group.isStagedFocused = False
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
