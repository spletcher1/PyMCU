import array
import datetime

import Enums
import Instruction
import Paradigm
from Enums import INSTRUCTIONSETTYPE

PROGRAM_TYPE_NAMES = {
    INSTRUCTIONSETTYPE.LINEAR: "Linear",
    INSTRUCTIONSETTYPE.REPEATING: "Repeating",
    INSTRUCTIONSETTYPE.CIRCADIAN: "Circadian",
    INSTRUCTIONSETTYPE.CONSTANT: "Constant",
}


def ProgramTypeFromString(text):
    for programType, name in PROGRAM_TYPE_NAMES.items():
        if text.strip().lower() == name.lower():
            return programType
    raise ValueError("ProgramType must be Linear, Repeating, Circadian or Constant, not '{}'".format(text.strip()))


def LinkageFromString(text):
    values = [v.strip() for v in text.split(",")]
    try:
        linkage = [int(v) for v in values]
    except ValueError:
        raise ValueError("Linkage must be 12 whole numbers") from None
    if len(linkage) != 12:
        raise ValueError("Linkage must have 12 values, not {}".format(len(linkage)))
    return array.array("i", linkage)


class InstructionSet:
    """A DFM's (or the Environmental Monitor's) Intervals and how they follow each other."""
    def __init__(self):
        self.Clear()

    def __str__(self):
        s = "Program Type: " + PROGRAM_TYPE_NAMES[self.instructionSetType] + "\n"
        for i in self.instructions:
            s+=str(i)+"\n"
        return s

    def __len__(self):
        return len(self.instructions)

    def Clear(self):
        self.instructions=[]
        self.instructionSetType = INSTRUCTIONSETTYPE.LINEAR
        self.linkage = array.array("i",[1,2,3,4,5,6,7,8,9,10,11,12])
        # Old-style settings that old Interval lines (14 numbers) use.
        self.optoDelay=0
        self.optoDecay=0
        self.optoFrequency=40
        self.optoPulseWidth=8
        self.maxTimeOn = 0

    def GetDuration(self):
        tmp = datetime.timedelta(seconds=0)
        for i in self.instructions:
            tmp = tmp+i.duration
        return tmp

    #region Adding Intervals
    def AddInterval(self, darkstate, paradigm, thresholds, minutes):
        start = self.instructions[-1].GetElapsedEnd() if self.instructions else datetime.timedelta(seconds=0)
        tmp = Instruction.DFMInstruction(darkstate, paradigm, datetime.timedelta(seconds=minutes*60), start)
        tmp.SetOptoValues(thresholds)
        self.instructions.append(tmp)

    def AddSimpleInstruction(self,darkstate,dur,startt):
        tmp = Instruction.DFMInstruction(darkstate, Paradigm.Paradigm.Idle(), dur, startt)
        self.instructions.append(tmp)

    @staticmethod
    def _ParseOldValues(tokens):
        """Dark state, thresholds and minutes from an old Interval line (14 or 19 numbers)."""
        if len(tokens) not in (14, 19):
            raise Paradigm.ParadigmError("An Interval line without a Paradigm name has 14 or 19 numbers, not {}".format(len(tokens)))
        try:
            values = [int(t) for t in tokens[:-1]]
            minutes = float(tokens[-1])
        except ValueError:
            raise Paradigm.ParadigmError("Interval values must be numbers") from None
        if values[0] not in (0, 1):
            raise Paradigm.ParadigmError("The first Interval value (dark running) must be 0 or 1")
        darkstate = Enums.DARKSTATE.ON if values[0] == 1 else Enums.DARKSTATE.OFF
        thresholds = []
        for t in values[1:13]:
            if t < -1:
                raise Paradigm.ParadigmError("Thresholds are 0 (always on), -1 (always off) or a signal level, not {}".format(t))
            thresholds.append(Instruction.OFF if t > 1023 else t)
        if minutes <= 0:
            raise Paradigm.ParadigmError("An Interval must last more than 0 minutes")
        return darkstate, thresholds, values[13:], minutes

    def AddLegacyInterval(self, tokens):
        """An Interval line in the form used before Paradigms: dark, 12 thresholds, then either the
        minutes or frequency, pulse width, decay, delay, max time on and the minutes."""
        darkstate, thresholds, opto, minutes = self._ParseOldValues(tokens)
        if opto:
            paradigm = Paradigm.Paradigm.Legacy(*opto)
        else:
            paradigm = Paradigm.Paradigm.Legacy(self.optoFrequency, self.optoPulseWidth, self.optoDecay,
                                                self.optoDelay, self.maxTimeOn)
        self.AddInterval(darkstate, paradigm, thresholds, minutes)

    def AddEnvMonInterval(self, tokens):
        """An Environmental Monitor Interval: dark, relay and pin states (in the threshold slots)
        and the minutes."""
        darkstate, states, _, minutes = self._ParseOldValues(tokens)
        self.AddInterval(darkstate, Paradigm.Paradigm.Idle(), states, minutes)
    #endregion

    #region Which Interval is running
    def _IndexAt(self, seconds):
        for index, i in enumerate(self.instructions):
            if i.elapsedStart.total_seconds() <= seconds < i.GetElapsedEnd().total_seconds():
                return index
        return len(self.instructions)-1

    def GetPosition(self, now, startTime):
        """(instruction, Interval index from 0, Cycle from 1), or (None, None, None) before the start."""
        if not self.instructions:
            return None, None, None
        if self.instructionSetType == INSTRUCTIONSETTYPE.CIRCADIAN:
            # Circadian programs run on the time of day.
            seconds = now.hour*3600 + now.minute*60 + now.second + now.microsecond/1e6
            cycle = (now.date() - startTime.date()).days + 1
        else:
            seconds = (now - startTime).total_seconds()
            if seconds <= 0:
                return None, None, None
            cycle = 1
            if self.instructionSetType == INSTRUCTIONSETTYPE.CONSTANT:
                return self.instructions[0], 0, 1
            if self.instructionSetType == INSTRUCTIONSETTYPE.REPEATING:
                total = self.instructions[-1].GetElapsedEnd().total_seconds()
                cycle = int(seconds // total) + 1
                seconds = seconds % total
        index = self._IndexAt(seconds)
        return self.instructions[index], index, cycle

    def GetInstruction(self, now, startTime):
        return self.GetPosition(now, startTime)[0]
    #endregion

    def Paradigms(self):
        seen = {}
        for i in self.instructions:
            seen.setdefault(i.paradigm.name, i.paradigm)
        return list(seen.values())

    def FirmwareNeeded(self, version=None):
        """Why DFM firmware with this version tuple can't run these Intervals, one reason per
        Paradigm in order and without repeats, or empty. Without a version, only what needs
        4.0.0 is reported (see Paradigm.FirmwareNeeded)."""
        reasons = []
        for p in self.Paradigms():
            reason = p.FirmwareNeeded(version)
            if reason is not None and reason not in reasons:
                reasons.append(reason)
        return reasons

    def Validate(self):
        """A problem with the Intervals as a whole, or None."""
        if(self.instructionSetType==INSTRUCTIONSETTYPE.CIRCADIAN):
            if(len(self.instructions)==0):
                return "A Circadian program needs Intervals"
            totalMinutes = self.instructions[-1].GetElapsedEnd().total_seconds()/60
            if(totalMinutes!=1440):
                return "Circadian Intervals must add up to 1440 minutes, not {:g}".format(totalMinutes)
        return None

    def ToString(self,duration,startTime):
        s="Linkage: " + ",".join(str(i) for i in self.linkage) + "\n"
        s+="Program Type: " + PROGRAM_TYPE_NAMES[self.instructionSetType] + "\n"
        for i in self.instructions:
            if (i.elapsedStart < duration):
                tmp = (startTime+i.elapsedStart).strftime("%m/%d/%Y %H:%M:%S")
                s+="(" + tmp +") "
                s+=str(i)+"\n"
        return s
