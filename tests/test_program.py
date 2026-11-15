"""Program loading: [Paradigm] sections, new and old Interval lines, errors and Interval timing."""
import support  # noqa: F401  (must come first)

import datetime
import os
import types
import unittest
from unittest import mock

import DFMGroup
import Enums
import Instruction
import MessagesList
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
        self.assertEqual(len(program.theParadigms), 9)
        p = program.theParadigms
        self.assertEqual([p[n].countsContact for n in ("pr", "prexp", "fr5s", "pr10", "fr5")],
                         [True, True, True, False, False])
        self.assertEqual(p["pr"].SettingsWords(), [500, 0, 100, 100, 65535])
        self.assertEqual(p["fr5s"].SettingsWords()[:2], [500, 500])
        dfm5 = program.theInstructionSets[5]
        self.assertEqual([i.paradigm.name for i in dfm5.instructions], ["Closed", "PR"])
        self.assertEqual(dfm5.instructions[1].elapsedStart, datetime.timedelta(minutes=30))
        self.assertEqual(list(dfm5.instructions[0].optoValues[:2]), [20, Instruction.OFF])
        self.assertEqual(program.theInstructionSets[1].instructions[0].optoValues[0], Instruction.ON)
        self.assertEqual(dfm5.instructions[0].theDarkState, Enums.DARKSTATE.ON)

    def test_description_follows_interval_line_order(self):
        # Program.txt writes each Interval as the Program file does: Paradigm, then Dark or Lit.
        program, ok = Load("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: 1\nInterval: A, Dark, {}, 10".format(WELLS))
        self.assertTrue(ok, program.loadError)
        self.assertIn(") A, Dark, " + WELLS + ", 10 min\n", program.GetProgramDescription())

    def test_description_keeps_the_program_thresholds_after_a_baseline(self):
        # A recording's Baselines change the Thresholds sent, not the Program, so the next recording
        # with the same Program loaded writes the Program's thresholds to its Program.txt.
        program, ok = Load("[Paradigm A]\nType: OpenLoop\n[DFM]\nID: 1\nInterval: A, Dark, {}, 10".format(WELLS))
        self.assertTrue(ok, program.loadError)
        instruction = program.theInstructionSets[1].instructions[0]
        instruction.SetBaseline([10] * 12)
        self.assertEqual(list(instruction.adjustedThresholds[:2]), [30, Instruction.OFF])
        self.assertIn(") A, Dark, " + WELLS + ", 10 min\n", program.GetProgramDescription())

    def test_circadian_description_lists_every_interval_at_its_clock_time(self):
        # Circadian Intervals run on the time of day. At 14:00 Interval 2 (10:00 to midnight) is
        # running, though it starts 10 h after midnight and the recording lasts 6 h from 13:45.
        lines = ["[Paradigm A]", "Type: OpenLoop", "[Paradigm B]", "Type: OpenLoop", "[DFM]", "ID: 1",
                 "ProgramType: Circadian", "Interval: A, Lit, {}, 600".format(WELLS),
                 "Interval: B, Dark, {}, 840".format(WELLS)]
        program, ok = Load("\n".join(lines))
        self.assertTrue(ok, program.loadError)
        program.startTime = datetime.datetime(2026, 3, 2, 13, 45)
        program.experimentDuration = datetime.timedelta(hours=6)
        _, index, cycle = program.theInstructionSets[1].GetPosition(
            datetime.datetime(2026, 3, 2, 14, 0), program.startTime)
        self.assertEqual((index, cycle), (1, 1))
        text = program.GetProgramDescription()
        self.assertIn("(03/02/2026 00:00:00) A, Lit, " + WELLS + ", 600 min\n", text)
        self.assertIn("(03/02/2026 10:00:00) B, Dark, " + WELLS + ", 840 min\n", text)

    def test_defaults(self):
        program, ok = Load("""
[Paradigm A]
Type: ProgressiveRatio
ActivationMs: 500
Step: 10
[Paradigm B]
Type: ProgressiveRatio
Counter: Events
ActivationMs: 500
Series: exponential
[Paradigm E]
Type: ProgressiveRatio
Counter: Events
ActivationMs: 500
Step: 10
[DFM]
ID: 1
Interval: A, Lit, {}, 10
""".format(WELLS))
        self.assertTrue(ok, program.loadError)
        a, b, e = program.theParadigms["a"], program.theParadigms["b"], program.theParadigms["e"]
        self.assertEqual((a.frequency, a.pulseWidth, a.eventGapMs, a.acclimation), (40, 8, 100, 0))
        # Without a Counter, a ratio Paradigm counts ms of contact: Step 10 is 10 ms, FirstRequirement
        # defaults to 10 ms and Cap to 655350 ms, sent in the DFM's 10 ms units.
        self.assertTrue(a.countsContact)
        self.assertEqual((a.Get("FirstRequirement"), a.Get("Cap")), (10, 655350))
        self.assertEqual(a.SettingsWords(), [500, 0, 1, 1, 65535])
        self.assertEqual(a.InstructionFlags(), Paradigm.INSTRUCTION_COUNT_CONTACT)
        # Counter: Events keeps the Event defaults.
        self.assertEqual(b.SettingsWords(), [500, 1, 5000, 200, 65535])
        self.assertEqual((e.countsContact, e.SettingsWords(), e.InstructionFlags()), (False, [500, 0, 1, 10, 65535], 0))

    def test_contact_counter(self):
        program, ok = Load("""
[Paradigm C]
Type: ProgressiveRatio
Counter: Contact
ActivationMs: 500
FirstRequirement: 1000
Step: 1000
[Paradigm D]
Type: ProgressiveRatio
Counter: contact
ActivationMs: 500
Step: 20
[Paradigm X]
Type: ProgressiveRatio
Counter: Contact
ActivationMs: 500
Series: Exponential
Scale: 5000
[Paradigm F]
Type: FixedRatio
Counter: Contact
ActivationMs: 500
Ratio: 2000
[Paradigm E]
Type: ProgressiveRatio
Counter: Events
ActivationMs: 500
Step: 5
[DFM]
ID: 1
Interval: C, Lit, {}, 10
""".format(WELLS))
        self.assertTrue(ok, program.loadError)
        p = program.theParadigms
        self.assertTrue(p["c"].countsContact)
        # The DFM gets the ms of contact in its 10 ms units.
        self.assertEqual(p["c"].SettingsWords(), [500, 0, 100, 100, 65535])
        # Defaults: FirstRequirement 10 ms, Cap 655350 ms.
        self.assertEqual((p["d"].Get("FirstRequirement"), p["d"].Get("Cap")), (10, 655350))
        self.assertEqual(p["d"].SettingsWords(), [500, 0, 1, 2, 65535])
        self.assertEqual(p["x"].SettingsWords(), [500, 1, 500000, 200, 65535])
        self.assertEqual(p["f"].SettingsWords(), [500, 200, 0, 0, 0])
        self.assertEqual((p["e"].countsContact, p["e"].SettingsWords()), (False, [500, 0, 1, 5, 65535]))
        self.assertIn("ActivationMs 500 ms, Counter Contact, Series Arithmetic, FirstRequirement 1000 ms, "
                      "Step 1000 ms, Cap 655350 ms", p["c"].Describe())
        # Counter is always written, so Program.txt says which a ratio Paradigm counted; files
        # written before 4.0.1 have none and counted Events.
        self.assertIn("ActivationMs 500 ms, Counter Events, Series Arithmetic, FirstRequirement 1, Step 5, Cap 65535,",
                      p["e"].Describe())

    def test_contact_counter_errors(self):
        pr = "[Paradigm A]\nType: ProgressiveRatio\nActivationMs: 5\n"
        self.ExpectError("[Paradigm A]\nType: ClosedLoop\nCounter: Contact", 3, "ClosedLoop Paradigms don't use Counter")
        self.ExpectError(pr + "Counter: Licks\nStep: 10", 4, "Counter must be Events or Contact")
        self.ExpectError(pr + "Counter: Contact\nStep: 1005", 5, "must be a multiple of 10")
        self.ExpectError(pr + "Counter: Contact\nStep: 700000", 5, "655350")
        self.ExpectError(pr + "Counter: Events\nStep: 70000", 5, "Step must be from 0 to 65535, not 70000")
        self.ExpectError("[Paradigm A]\nType: FixedRatio\nActivationMs: 5\nCounter: Contact\nRatio: 5", 5,
                         "must be a multiple of 10")
        # A Program written for Events, from before Contact was the default, is caught and told why.
        self.ExpectError(pr + "Step: 5", 4, "Step is in ms of contact (Counter: Contact, the default)")
        self.ExpectError(pr + "Step: 5", 4, "add 'Counter: Events'")
        self.ExpectError("[Paradigm A]\nType: FixedRatio\nActivationMs: 5\nRatio: 3", 4, "add 'Counter: Events'")
        # Exponential's Scale of 5 is Events; in ms of contact it has to be given.
        self.ExpectError(pr + "Series: Exponential", 1, "Scale is ms of contact and has no default")

    def test_only_ratio_paradigms_have_a_counter(self):
        # A ratio Paradigm counts Contact unless it says Events, however it was built; other types
        # have no Counter and never send the Contact flag.
        pr = Paradigm.Paradigm("X", Paradigm.ParadigmType.PROGRESSIVERATIO)
        self.assertEqual((pr.countsContact, pr.InstructionFlags()), (True, Paradigm.INSTRUCTION_COUNT_CONTACT))
        del pr.settings["Counter"]
        self.assertTrue(pr.countsContact)
        for paradigmType in (Paradigm.ParadigmType.CLOSEDLOOP, Paradigm.ParadigmType.FIXEDINTERVAL):
            other = Paradigm.Paradigm("Y", paradigmType)
            self.assertEqual((other.countsContact, other.InstructionFlags()), (False, 0))

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
        self.ExpectError("[Paradigm A]\nType: ProgressiveRatio\nActivationMs: 5\nStep: 1000\nScale: 3", 5,
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

    def test_opto_test_programs_cover_each_type(self):
        """The OptoTest programs are the worked examples of the Paradigm format: one type each,
        for every connected DFM (ID: All), with the comment at the top saying what to expect."""
        expected = {
            "OptoTest1_OpenLoop.txt": (Paradigm.ParadigmType.OPENLOOP, None, 1),
            "OptoTest2_ClosedLoop.txt": (Paradigm.ParadigmType.CLOSEDLOOP, None, 1),
            "OptoTest3_FixedInterval.txt": (Paradigm.ParadigmType.FIXEDINTERVAL, None, 1),
            "OptoTest4_NonFeeding.txt": (Paradigm.ParadigmType.NONFEEDING, None, 1),
            "OptoTest5_ProgressiveRatio.txt": (Paradigm.ParadigmType.PROGRESSIVERATIO, "the ProgressiveRatio Paradigm type needs firmware 4.0.0", 1),
            "OptoTest6_TrainingFirst.txt": (Paradigm.ParadigmType.FIXEDRATIO, "the FixedRatio Paradigm type needs firmware 4.0.0", 1),
            "OptoLidOutputTest.txt": (Paradigm.ParadigmType.OPENLOOP, None, 15),
        }
        for name, (paradigmType, needs, intervals) in expected.items():
            program, ok = LoadFile(name)
            self.assertTrue(ok, "{}: {}".format(name, program.loadError))
            with open(os.path.join(PROGRAMS, name), encoding="utf-8-sig") as f:
                self.assertGreaterEqual(sum(1 for line in f if line.startswith("#")), 8, name + " needs its comment")
            allSet = program.allInstructionSet
            self.assertIsNotNone(allSet, name + " should use ID: All")
            self.assertEqual(len(allSet.instructions), intervals, name)
            paradigm = allSet.instructions[0].paradigm
            self.assertEqual(paradigm.type, paradigmType, name)
            self.assertEqual(paradigm.FirmwareNeeded(), needs, name)
            self.assertEqual(program.experimentDuration, datetime.timedelta(minutes=5 if "Lid" in name else 10), name)

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
        self.assertTrue(ok, program.loadError)
        self.assertEqual(program.FirmwareNeeded(2), [])
        # DFMs 5 to 7 count contact, the default, which needs 4.0.1; DFM 8 counts Events, which
        # run on 4.0.0; DFM 6 does both.
        contact = "counting contact (Counter: Contact, the {} default) needs firmware 4.0.1; with 'Counter: Events' it runs on 4.0.0"
        pr, fr = contact.format("ProgressiveRatio"), contact.format("FixedRatio")
        self.assertEqual(program.FirmwareNeeded(5), [pr])
        self.assertEqual(program.FirmwareNeeded(6), [fr, "the FixedRatio Paradigm type needs firmware 4.0.0"])
        self.assertEqual(program.FirmwareNeeded(8), ["the ProgressiveRatio Paradigm type needs firmware 4.0.0"])
        for dfm, reasons in ((5, [pr]), (6, [fr]), (7, [pr]), (8, [])):
            self.assertEqual(program.FirmwareNeeded(dfm, (4, 0, 0)), reasons, dfm)
            self.assertEqual(program.FirmwareNeeded(dfm, (4, 0, 1)), [], dfm)

    def test_schedule_examples(self):
        # Each program type, keep-state across a threshold change, Adaptive and the Environmental Monitor.
        program, ok = LoadFile("ScheduleExamples.txt")
        self.assertTrue(ok, program.loadError)
        types = {d: program.theInstructionSets[d].instructionSetType for d in (1, 2, 3, 4)}
        self.assertEqual(types, {1: Enums.INSTRUCTIONSETTYPE.REPEATING, 2: Enums.INSTRUCTIONSETTYPE.CIRCADIAN,
                                 3: Enums.INSTRUCTIONSETTYPE.CONSTANT, 4: Enums.INSTRUCTIONSETTYPE.LINEAR})
        self.assertEqual(program.AdaptiveSettings(), (5.0, 50))
        circadian = program.theInstructionSets[2]
        start = datetime.datetime(2026, 3, 2, 13, 45)
        self.assertEqual([circadian.GetPosition(datetime.datetime(2026, 3, 3, h), start)[1:] for h in (3, 8, 20)],
                         [(0, 2), (1, 2), (2, 2)])
        dfm4 = program.theInstructionSets[4].instructions
        self.assertEqual([i.paradigm.name for i in dfm4], ["PR", "PR"])
        self.assertEqual([i.optoValues[0] for i in dfm4], [20, 30])
        self.assertEqual(program.theInstructionSets[99].instructionSetType, Enums.INSTRUCTIONSETTYPE.CIRCADIAN)
        self.assertEqual(program.FirmwareNeeded(4, (4, 0, 0))[0][:16], "counting contact")
        self.assertEqual(program.FirmwareNeeded(1, (1, 0, 5)), [])
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


ADAPTIVE = """
[General]
{}
[Paradigm A]
Type: ClosedLoop
[DFM]
ID: 1
Interval: A, Lit, {}, 10
"""


class AdaptiveBaselineSettings(unittest.TestCase):
    """Baseline: Adaptive and its settings (docs/adaptive-baseline-plan.md, Program file)."""
    def LoadGeneral(self, *lines):
        return Load(ADAPTIVE.format("\n".join(lines), WELLS))

    def test_adaptive_with_settings(self):
        # The settings may come before Baseline.
        program, ok = self.LoadGeneral("BaselineRatePerHour: 2.5", "BaselineCapCounts: 30", "Baseline: Adaptive")
        self.assertTrue(ok, program.loadError)
        self.assertTrue(program.autoBaseline)
        self.assertEqual(program.AdaptiveSettings(), (2.5, 30))
        self.assertIn("Baseline: Adaptive\nBaselineRatePerHour: 2.5\nBaselineCapCounts: 30\n", program.GetProgramDescription())

    def test_adaptive_defaults_are_written(self):
        program, ok = self.LoadGeneral("Baseline: adaptive")
        self.assertTrue(ok, program.loadError)
        self.assertEqual(program.AdaptiveSettings(), (5.0, 50))
        self.assertIn("Baseline: Adaptive\nBaselineRatePerHour: 5\nBaselineCapCounts: 50\n", program.GetProgramDescription())

    def test_yes_and_no_are_not_adaptive(self):
        for value, auto in (("Yes", True), ("No", False)):
            program, ok = self.LoadGeneral("Baseline: " + value)
            self.assertTrue(ok, program.loadError)
            self.assertEqual((program.autoBaseline, program.AdaptiveSettings()), (auto, None))
            self.assertIn("Baseline: {}\n".format(value), program.GetProgramDescription())
            self.assertNotIn("BaselineRatePerHour", program.GetProgramDescription())

    def test_refused(self):
        cases = [
            (("Baseline: Yes", "BaselineCapCounts: 40"), "Line 3: BaselineCapCounts needs Baseline: Adaptive"),
            (("BaselineRatePerHour: 5",), "Line 2: BaselineRatePerHour needs Baseline: Adaptive"),
            (("Baseline: Adaptive", "BaselineCapCounts: 5"), "Line 3: BaselineCapCounts must be at least 10"),
            (("Baseline: Adaptive", "BaselineCapCounts: 12.5"), "Line 3: BaselineCapCounts must be a whole number"),
            (("Baseline: Adaptive", "BaselineRatePerHour: 0"), "Line 3: BaselineRatePerHour must be a number of counts above 0"),
            (("Baseline: Adaptive", "BaselineRatePerHour: fast"), "Line 3: BaselineRatePerHour must be a number"),
            (("Baseline: Sometimes",), "Line 2: Baseline must be Yes, No or Adaptive"),
        ]
        for lines, error in cases:
            program, ok = self.LoadGeneral(*lines)
            self.assertFalse(ok, lines)
            self.assertTrue(program.loadError.startswith(error), (lines, program.loadError))

    def test_recording_start_passes_the_settings(self):
        program, ok = self.LoadGeneral("Baseline: Adaptive", "BaselineRatePerHour: 3")
        group = StagedProgram().Group()
        group.currentProgram = program
        group.theMessageList = MessagesList.MessageList()
        group.NewMessage = group.WriteStarter = group.SetNormalProgramReadInterval = lambda *a: None
        with mock.patch.object(DFMGroup.time, "sleep"):
            group.StartRecording()
        self.assertEqual([d.adaptiveSettings for d in group.theDFMs.values()], [(3.0, 50)] * 2)
        self.assertTrue(all(d.isCalculatingBaseline for d in group.theDFMs.values()))


if __name__ == "__main__":
    unittest.main()
