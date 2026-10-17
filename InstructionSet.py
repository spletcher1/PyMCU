import Instruction
from Enums import INSTRUCTIONSETTYPE
import Enums
import datetime
import array

# Ranges of the Program file's opto settings. Times are the 4-byte fields of firmware 2.0.0 and
# later (1.0.5 boards are checked separately, see Instruction.FirmwareNeeded). The frequency and
# pulse width also take the forms firmware 2.0.0 added: count x 512 + hertz asks for that many
# training Activations, and 32768 + width asks for non-feeding activation.
MAX_TIME_MS = 4294967295
MAX_PULSE_WIDTH_MS = 1000
TRAINING_COUNT_UNIT = 512
NON_FEEDING_FLAG = 32768


class ProgramError(ValueError):
    """A Program file setting the DFMs can't use. The message names the line it is on."""


def _Where(lineNumber):
    return "line {}: ".format(lineNumber) if lineNumber else "General settings: "


def CheckedInt(name, text, lineNumber, low, high):
    """text as a whole number from low to high, else a ProgramError naming the line and setting."""
    try:
        value = int(text.strip())
    except ValueError:
        raise ProgramError(_Where(lineNumber) + "{} must be a whole number, not '{}'".format(name, text.strip()))
    if not low <= value <= high:
        raise ProgramError(_Where(lineNumber) + "{} must be {} to {}, not {}".format(name, low, high, value))
    return value


def CheckedFrequency(text, lineNumber):
    """OptoFrequency: 1 to 500 Hz, or the firmware 2.0.0 training form count x 512 + hertz."""
    value = CheckedInt("OptoFrequency", text, lineNumber, 0, 65535)
    hertz = value % TRAINING_COUNT_UNIT if value > Instruction.MAX_FREQUENCY_HZ else value
    if not 1 <= hertz <= Instruction.MAX_FREQUENCY_HZ:
        raise ProgramError(_Where(lineNumber) + "OptoFrequency must be 1 to 500 Hz, or count x 512 + hertz "
                           "(hertz 1 to 500) for training, not {}".format(value))
    return value


def CheckedPulseWidth(text, lineNumber):
    """OptoPW: 1 to 1000 ms, or 32768 + width (width 1 to 1000) for firmware 2.0.0 non-feeding activation."""
    value = CheckedInt("OptoPW", text, lineNumber, 0, 65535)
    width = value - NON_FEEDING_FLAG if value >= NON_FEEDING_FLAG else value
    if not 1 <= width <= MAX_PULSE_WIDTH_MS:
        raise ProgramError(_Where(lineNumber) + "OptoPW must be 1 to 1000 ms, or 32768 + width (width 1 to 1000) "
                           "for non-feeding activation, not {}".format(value))
    return value


def CheckOptoSettings(frequency, pulseWidth, decay, delay, maxTimeOn, lineNumber):
    """The pulse must fit inside one period; non-feeding activation and progressive ratio need an
    on time (with OptoDecay 0 the firmware lights each activation for 1 ms); and a training count
    needs progressive ratio, the only rule the firmware runs it before."""
    hertz = frequency % TRAINING_COUNT_UNIT if frequency > Instruction.MAX_FREQUENCY_HZ else frequency
    width = pulseWidth - NON_FEEDING_FLAG if pulseWidth >= NON_FEEDING_FLAG else pulseWidth
    if width * hertz >= 1000:
        raise ProgramError(_Where(lineNumber) + "OptoPW {} ms is not shorter than one period at {} Hz ({:.1f} ms)".format(
            width, hertz, 1000 / hertz))
    if pulseWidth >= NON_FEEDING_FLAG and decay <= 0:
        raise ProgramError(_Where(lineNumber) + "OptoPW {} is non-feeding activation, which needs OptoDecay above 0 "
                           "for the light's on time".format(pulseWidth))
    # Non-feeding activation takes precedence in the firmware, so this is progressive ratio only without it.
    isNonFeeding = pulseWidth >= NON_FEEDING_FLAG
    isProgressiveRatio = not isNonFeeding and delay > 0 and maxTimeOn > 0
    if isProgressiveRatio and decay <= 0:
        raise ProgramError(_Where(lineNumber) + "OptoDelay and MaxTimeOn both above 0 is progressive ratio, which needs "
                           "OptoDecay above 0 for the light's on time")
    # The firmware runs a training count only before progressive ratio and ignores it otherwise.
    if frequency > Instruction.MAX_FREQUENCY_HZ and not isProgressiveRatio:
        raise ProgramError(_Where(lineNumber) + "OptoFrequency {} asks for {} training Activations, which only run with "
                           "progressive ratio (OptoDelay and MaxTimeOn both above 0, OptoPW below 32768)".format(
                               frequency, frequency // TRAINING_COUNT_UNIT))


class InstructionSet:
    def __init__(self):
        self.Clear()
    def __str__(self):
        s = "Program Type: "
        if(self.instructionSetType == INSTRUCTIONSETTYPE.LINEAR):
            s+="Linear"
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.CIRCADIAN):
            s+="Circadian"
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.REPEATING):
            s+="Repeating"
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.CONSTANT):
            s+="Constant"

        s+="\n"
        for i in self.instructions:
            s+=str(i)+"\n"
        return s
    def __len__(self):
        return len(self.instructions)

    def RaiseError(self, s):
        print(s)
    def GetDuration(self):
        tmp = datetime.timedelta(seconds=0)
        for i in self.instructions:
            tmp = tmp+i.duration
        return tmp

    def _GetInstruction(self,td : datetime.timedelta):
        if(td.total_seconds()<=0):
            return None
        for i in self.instructions:
            if (td.total_seconds() > i.elapsedStart.total_seconds()) and (td.total_seconds() <= i.GetElapsedEnd().total_seconds()):
                return i
        return self.instructions[-1]

    def GetInstruction(self,now,startTime):
        if(len(self.instructions) <=0) : return None
        if(self.instructionSetType == INSTRUCTIONSETTYPE.LINEAR):
            return self._GetInstruction(now-startTime)
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.CIRCADIAN):
            # We are now assuming circaidan programs start at midnight
            elapsedSecondsFromMidnight = now.hour*60*60+now.minute*60+now.second
            return self._GetInstruction(datetime.timedelta(seconds=elapsedSecondsFromMidnight))
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.REPEATING):
            ts = now-startTime
            lastInstruction = self.instructions[-1]
            diff = ts.total_seconds() % lastInstruction.GetElapsedEnd().total_seconds()
            return self._GetInstruction(datetime.timedelta(seconds=diff))
        else:
            return None

    def FirmwareNeeded(self):
        """The reasons, in order and without repeats, that firmware 1.0.5 can't run these
        Intervals (see Instruction.DFMInstruction.FirmwareNeeded). Empty if it can."""
        reasons = []
        for i in self.instructions:
            reason = i.FirmwareNeeded()
            if(reason is not None and reason not in reasons):
                reasons.append(reason)
        return reasons


    def Validate(self):
        if(self.instructionSetType==INSTRUCTIONSETTYPE.CIRCADIAN):
            if(len(self.instructions)==0):
                return False
            totalSeconds = self.instructions[-1].GetElapsedEnd().total_seconds()
            if(totalSeconds!=86400):
                return False
            else:
                return True
        else:
            return True

    def AddSimpleInstruction(self,darkstate,dur,startt):
        tmp= Instruction.DFMInstruction(darkstate,self.optoFrequency,self.optoPulseWidth,self.optoDecay,self.optoDelay,self.maxTimeOn,dur,startt)
        self.instructions.append(tmp)
        return True

    def AddDefaultInstruction(self):
        self.AddInstruction(Instruction.DFMInstruction())

    def AddInstruction(self, instruct:Instruction.DFMInstruction):
        if(len(self.instructions)==0):
            referencedStart = datetime.timedelta(seconds=0)
        else:
            lastoi = self.instructions[-1]
            referencedStart = lastoi.GetElapsedEnd()
        tmp=Instruction.DFMInstruction(instruct.theDarkState,instruct.frequency,instruct.pulseWidth,instruct.decay,instruct.delay,instruct.maxTimeOn,instruct.duration,referencedStart)
        tmp.SetOptoValues(instruct.optoValues)
        self.instructions.append(tmp)
        return True

    def AddInstructionFromString(self,s,lineNumber=0):
        """Adds the Interval on one 'Interval:' line: dark, the 12 thresholds, then either the
        duration in minutes (14 numbers) or the frequency, pulse width, decay, delay, max time
        on and the duration (19 numbers). Raises ProgramError, naming the line, for anything
        the DFMs can't run."""
        ss = [x.strip() for x in s.split(",")]
        if(len(ss) not in (14, 19)):
            raise ProgramError(_Where(lineNumber) + "an Interval needs 14 or 19 numbers, not {}".format(len(ss)))
        ds = Enums.DARKSTATE.ON if CheckedInt("dark (the first number)", ss[0], lineNumber, 0, 1) == 1 else Enums.DARKSTATE.OFF
        ov = array.array("i",(-1 for jj in range(0,12)))
        for x in range(0,12):
            ov[x] = CheckedInt("threshold {}".format(x + 1), ss[x+1], lineNumber, -1, 65535)
            if(ov[x]>1023):
                ov[x]=-1    # off, as the firmware reads anything above 1050
        if(len(ss)==14):
            freq, pw = self.optoFrequency, self.optoPulseWidth
            decay, delay, maxTime = self.optoDecay, self.optoDelay, self.maxTimeOn
        ## If Freq, PW, Decay, Delay, and MaxTime are also defined
        else:
            freq = CheckedFrequency(ss[13], lineNumber)
            pw = CheckedPulseWidth(ss[14], lineNumber)
            decay = CheckedInt("OptoDecay", ss[15], lineNumber, 0, MAX_TIME_MS)
            delay = CheckedInt("OptoDelay", ss[16], lineNumber, 0, MAX_TIME_MS)
            maxTime = CheckedInt("MaxTimeOn", ss[17], lineNumber, 0, MAX_TIME_MS)
        try:
            minutes = float(ss[-1])
        except ValueError:
            raise ProgramError(_Where(lineNumber) + "the duration (the last number) must be in minutes, not '{}'".format(ss[-1]))
        CheckOptoSettings(freq, pw, decay, delay, maxTime, lineNumber)
        tmp = Instruction.DFMInstruction(ds,freq,pw,decay,delay,maxTime,datetime.timedelta(seconds=minutes*60),0)
        tmp.SetOptoValues(ov)
        self.AddInstruction(tmp)

    def SetProgramTypeFromString(self,pt):
        if(pt.lower()=="linear"):
            self.instructionSetType = INSTRUCTIONSETTYPE.LINEAR
        elif(pt.lower()=="repeating"):
            self.instructionSetType = INSTRUCTIONSETTYPE.REPEATING
        elif(pt.lower()=="circadian"):
            self.instructionSetType = INSTRUCTIONSETTYPE.CIRCADIAN
        elif(pt.lower()=="constant"):
            self.instructionSetType = INSTRUCTIONSETTYPE.CONSTANT
        else:
            self.instructionSetType = INSTRUCTIONSETTYPE.CONSTANT

    def SetLinkageFromString(self,lk):
        ss = lk.split(",")
        if(len(ss)==12):
            for x in range(0,12):
                self.linkage[x]=int(ss[x])

    def Clear(self):
        self.instructions=[]
        self.instructionSetType = INSTRUCTIONSETTYPE.LINEAR
        self.linkage = array.array("i",[1,2,3,4,5,6,7,8,9,10,11,12])
        self.optoDelay=0
        self.optoDecay=0
        self.optoFrequency=40
        self.optoPulseWidth=8
        self.maxTimeOn = 0


    def ToString(self,duration,startTime):
        s="Linkage: "
        for i in self.linkage:
            s+=str(i)+","
        s=s[:-1]
        s+="\n"
        s+="Opto Frequency: " + str(self.optoFrequency) +"Hz\n"
        s+="Opto Pulsewidth: " + str(self.optoPulseWidth) + "ms\n"
        s+="Opto Delay: " + str(self.optoDelay) + "ms\n"
        s+="Opto Decay: " + str(self.optoDecay) + "ms\n"
        s+="Max Time On: " + str(self.maxTimeOn) + "ms\n"

        s += "Program Type: "
        if(self.instructionSetType == INSTRUCTIONSETTYPE.LINEAR):
            s+="Linear"
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.CIRCADIAN):
            s+="Circadian"
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.REPEATING):
            s+="Repeating"
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.CONSTANT):
            s+="Constant"
        s+="\n"

        for i in self.instructions:
            if (i.elapsedStart < duration):
                tmp = (startTime+i.elapsedStart).strftime("%m/%d/%Y %H:%M:%S")
                s+="(" + tmp +") "
                s+=str(i)+"\n"

        return s
#region Testing
def ModuleTest():
    tmp = InstructionSet()
    tmp.instructionSetType = INSTRUCTIONSETTYPE.CIRCADIAN
    tmp.AddDefaultInstruction()
    tmp.AddDefaultInstruction()
    tmp.AddInstructionFromString("1,10,11,12,13,14,15,16,17,18,19,20,21,30,12,1000,0,0,30,2")
    tmp.SetProgramTypeFromString("circadian")
    tmp.SetLinkageFromString("1,2,3,1,5,6,7,1,9,10,1,12")
    print(tmp.ToString(datetime.timedelta(minutes=800),datetime.datetime.today()-datetime.timedelta(minutes=800)))



if __name__=="__main__" :
    ModuleTest()
#endregion
