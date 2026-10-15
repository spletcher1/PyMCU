import array
import datetime

import Enums
import Event
import Instruction
import InstructionSet
import Message
import Paradigm

ENVMON_ID = 99
# Settings each section takes (lower case).
_GENERAL_KEYS = {"starttime", "expdurationmin", "programtype", "optofrequency", "optopw", "optodecay",
                 "optodelay", "maxtimeon", "linkage", "baseline"}
_DFM_KEYS = {"id", "programtype", "linkage", "optofrequency", "optopw", "optodecay", "optodelay",
             "maxtimeon", "interval"}
_ENVMON_KEYS = {"id", "programtype", "interval"}
_OLD_OPTO_KEYS = {"optofrequency": "optoFrequency", "optopw": "optoPulseWidth", "optodecay": "optoDecay",
                  "optodelay": "optoDelay", "maxtimeon": "maxTimeOn"}


class ProgramError(Exception):
    """A problem in a Program file, with the line it is on."""
    def __init__(self, message, lineNumber=None):
        super().__init__(message)
        self.lineNumber = lineNumber

    def __str__(self):
        message = self.args[0]
        return "Line {}: {}".format(self.lineNumber, message) if self.lineNumber else message


def _ParseStartTime(text):
    text = text.strip()
    for form in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
        try:
            return datetime.datetime.strptime(text, form)
        except ValueError:
            pass
    today = datetime.datetime.today().strftime("%m/%d/%Y")
    for form in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M"):
        try:
            return datetime.datetime.strptime(today + " " + text, form)
        except ValueError:
            pass
    raise ValueError("StartTime must be HH:MM, HH:MM:SS or MM/DD/YYYY HH:MM:SS, not '{}'".format(text))


def _ParseInt(text, name):
    try:
        return int(text.strip())
    except ValueError:
        raise ValueError("{} must be a whole number, not '{}'".format(name, text.strip())) from None


class MCUProgram():
    Program_message = Event.Event()

    def __init__(self):
        self.theInstructionSets = {}
        self.ClearProgram()

    def __str__(self):
        return self.GetProgramDescription()

    def ClearProgram(self):
        ddt = datetime.datetime.today() + datetime.timedelta(minutes=1)
        self.startTime = datetime.datetime(ddt.year, ddt.month, ddt.day, ddt.hour, ddt.minute, 0)
        self.experimentDuration = datetime.timedelta(minutes=1)
        self.theInstructionSets.clear()
        self.theParadigms = {}
        self.optoFrequency = 40
        self.optoPulseWidth= 8
        self.optoDecay= 0
        self.optoDelay= 0
        self.maxTimeOn = 0
        self.globalLinkage = array.array("i",[1,2,3,4,5,6,7,8,9,10,11,12])
        self.globalPType = Enums.INSTRUCTIONSETTYPE.LINEAR
        self.autoBaseline = True
        self.isActive = False
        self.isProgramLoaded = False
        self.loadError = ""

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        MCUProgram.Program_message.notify(tmp)
    def GetEndTime(self):
        return self.startTime + self.experimentDuration

    def IsDuringExperiment(self):
        t = datetime.datetime.today()
        return self.startTime < t < self.GetEndTime()
    def IsBeforeExperiment(self):
        return datetime.datetime.today() < self.startTime
    def IsAfterExperiment(self):
        return datetime.datetime.today() > self.GetEndTime()

    def GetProgramDescription(self):
        if(not self.isProgramLoaded):
            if(len(self.theInstructionSets)<1):
                return "None"
            s="***ALL DFM***\n"
            s+="Start Time: " + self.startTime.strftime("%m/%d/%Y %H:%M:%S")+"\n"
            s+="End Time: " + self.GetEndTime().strftime("%m/%d/%Y %H:%M:%S")+"\n"
            s+="Duration: " +  "{:g}".format(self.experimentDuration.total_seconds()/60) + " min\n"
            s+="Linkage: " + ",".join(str(i) for i in self.globalLinkage) + "\n"
            s+="Baseline: " + ("Yes" if self.autoBaseline else "No") + "\n"
            s+=str(next(iter(self.theInstructionSets.values())))
            return s
        s="Start Time: " + self.startTime.strftime("%m/%d/%Y %H:%M:%S")+"\n"
        s+="End Time: " + self.GetEndTime().strftime("%m/%d/%Y %H:%M:%S")+"\n"
        s+="Duration: " +  "{:g}".format(self.experimentDuration.total_seconds()/60) + " min\n"
        s+="Default Linkage: " + ",".join(str(i) for i in self.globalLinkage) + "\n"
        s+="Default Program Type: " + InstructionSet.PROGRAM_TYPE_NAMES[self.globalPType] + "\n"
        s+="Baseline: " + ("Yes" if self.autoBaseline else "No") + "\n"
        paradigms = {}
        for key, value in self.theInstructionSets.items():
            if key != ENVMON_ID:
                for p in value.Paradigms():
                    paradigms.setdefault(p.name, p)
        if paradigms:
            s+="\nParadigms:\n"
            for p in paradigms.values():
                s+=p.Describe()+"\n"
        for (key, value) in sorted(self.theInstructionSets.items()):
            s+="\n"
            s += "***Env Mon***\n" if key==ENVMON_ID else "***DFM " + str(key) + "***\n"
            s+=value.ToString(self.experimentDuration, self.startTime)
        return s

    def CreateSimpleProgram(self,starttime,dur):
        # This will create a "linear" experiment with the current begin time and duration.
        self.ClearProgram()
        self.startTime=starttime
        self.experimentDuration=dur
        for i in range(0,99):
            self.AddSimpleProgram(i,dur)

    def AddSimpleProgram(self,dfmid,dur):
        # Every Well Off for the whole experiment.
        instruct = InstructionSet.InstructionSet()
        instruct.linkage = self.globalLinkage[:]
        instruct.instructionSetType = self.globalPType
        instruct.AddSimpleInstruction(Enums.DARKSTATE.OFF,dur,datetime.timedelta(seconds=0))
        self.theInstructionSets[dfmid]=instruct

    #region Loading
    def LoadProgram(self, lines, dfmList):
        """Loads a Program file. On a problem, nothing is loaded and loadError says what and where."""
        self.ClearProgram()
        try:
            self._Load(lines, dfmList)
        except (ProgramError, Paradigm.ParadigmError) as e:
            message = str(e) if isinstance(e, ProgramError) else str(ProgramError(str(e), e.lineNumber))
            self.ClearProgram()
            self.loadError = message
            self.NewMessage(0,datetime.datetime.today(),0,"Program load error. "+message,Enums.MESSAGETYPE.NOTICE)
            return False
        self.isProgramLoaded = True
        return True

    @staticmethod
    def _Sections(lines):
        """[(name, line number, [(key, value, line number)])] from a Program file."""
        sections = []
        for lineNumber, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                sections.append((line[1:-1].strip(), lineNumber, []))
                continue
            if not sections:
                raise ProgramError("Expected a section such as [General] before this line", lineNumber)
            if ":" not in line:
                raise ProgramError("Expected 'Setting: value'", lineNumber)
            key, value = line.split(":", 1)
            sections[-1][2].append((key.strip(), value.strip(), lineNumber))
        return sections

    def _Load(self, lines, dfmList):
        sections = self._Sections(lines)
        kinds = []
        for name, lineNumber, items in sections:
            words = name.split()
            kind = words[0].lower() if words else ""
            if kind == "paradigm" and len(words) == 2:
                kinds.append(("paradigm", words[1], lineNumber, items))
            elif kind in ("general", "dfm", "envmon") and len(words) == 1:
                kinds.append((kind, None, lineNumber, items))
            else:
                raise ProgramError("Unknown section [{}]. Sections: [General], [Paradigm NAME], [DFM], [ENVMON]".format(name), lineNumber)

        # [General] first: DFM sections start from its values.
        for kind, _, _, items in kinds:
            if kind == "general":
                for key, value, lineNumber in items:
                    self._GeneralSetting(key, value, lineNumber)
        for kind, name, lineNumber, items in kinds:
            if kind == "paradigm":
                if name.lower() in self.theParadigms:
                    raise ProgramError("Paradigm {} is defined twice".format(name), lineNumber)
                self.theParadigms[name.lower()] = Paradigm.Paradigm.FromSettings(name, items, lineNumber)
        for kind, _, lineNumber, items in kinds:
            if kind in ("dfm", "envmon"):
                self._DeviceSection(kind, lineNumber, items)

        if(self.experimentDuration.total_seconds()==0):
            for value in self.theInstructionSets.values():
                if value.GetDuration() > self.experimentDuration:
                    self.experimentDuration = value.GetDuration()

        for key, value in self.theInstructionSets.items():
            problem = value.Validate()
            if problem:
                raise ProgramError("{}: {}".format("Env Mon" if key==ENVMON_ID else "DFM {}".format(key), problem))

        if dfmList is not None:
            # Only DFMs that are present, which keeps the description short.
            present = {d.ID for d in dfmList.values()}
            self.theInstructionSets = {k: v for k, v in self.theInstructionSets.items() if k in present}
            for d in dfmList.values():
                if d.ID not in self.theInstructionSets:
                    self.AddSimpleProgram(d.ID,self.experimentDuration)
                    ss="DFM " + str(d.ID) + " not listed in program file. Adding simple program"
                    self.NewMessage(0,datetime.datetime.today(),0,ss,Enums.MESSAGETYPE.NOTICE)

    def _GeneralSetting(self, key, value, lineNumber):
        k = key.lower()
        try:
            if k not in _GENERAL_KEYS:
                raise ValueError("Unknown [General] setting '{}'".format(key))
            if k == "starttime":
                self.startTime = _ParseStartTime(value)
            elif k == "expdurationmin":
                minutes = float(value)
                if minutes < 0:
                    raise ValueError("ExpDurationMin can't be negative")
                self.experimentDuration = datetime.timedelta(minutes=minutes)
            elif k == "programtype":
                self.globalPType = InstructionSet.ProgramTypeFromString(value)
            elif k == "linkage":
                self.globalLinkage = InstructionSet.LinkageFromString(value)
            elif k == "baseline":
                if value.lower() not in ("yes", "no"):
                    raise ValueError("Baseline must be Yes or No")
                self.autoBaseline = value.lower() == "yes"
            else:
                setattr(self, _OLD_OPTO_KEYS[k], _ParseInt(value, key))
        except ValueError as e:
            raise ProgramError(str(e), lineNumber) from None

    def _NewSet(self):
        iset = InstructionSet.InstructionSet()
        for attribute in _OLD_OPTO_KEYS.values():
            setattr(iset, attribute, getattr(self, attribute))
        iset.linkage = self.globalLinkage[:]
        iset.instructionSetType = self.globalPType
        return iset

    def _DeviceSection(self, kind, sectionLine, items):
        allowed = _DFM_KEYS if kind == "dfm" else _ENVMON_KEYS
        title = "[DFM]" if kind == "dfm" else "[ENVMON]"
        iset = None
        if kind == "envmon":
            iset = self._NewSet()
            self.theInstructionSets[ENVMON_ID] = iset
        for key, value, lineNumber in items:
            k = key.lower()
            try:
                if k not in allowed:
                    raise ValueError("Unknown {} setting '{}'".format(title, key))
                if k == "id":
                    if kind == "envmon":
                        continue
                    if iset is not None:
                        raise ValueError("A [DFM] section has one ID; start a new [DFM] section for another DFM")
                    dfmid = _ParseInt(value, "ID")
                    if not 1 <= dfmid <= 98:
                        raise ValueError("DFM IDs are 1 to 98")
                    if dfmid in self.theInstructionSets:
                        raise ValueError("DFM {} has two [DFM] sections".format(dfmid))
                    iset = self._NewSet()
                    self.theInstructionSets[dfmid] = iset
                    continue
                if iset is None:
                    raise ValueError("A [DFM] section must start with its ID")
                if k == "programtype":
                    iset.instructionSetType = InstructionSet.ProgramTypeFromString(value)
                elif k == "linkage":
                    iset.linkage = InstructionSet.LinkageFromString(value)
                elif k == "interval":
                    tokens = [t.strip() for t in value.split(",")]
                    if kind == "envmon":
                        iset.AddEnvMonInterval(tokens)
                    else:
                        self._AddInterval(iset, tokens)
                else:
                    setattr(iset, _OLD_OPTO_KEYS[k], _ParseInt(value, key))
            except (ValueError, Paradigm.ParadigmError) as e:
                raise ProgramError(str(e), lineNumber) from None
        if kind == "dfm" and iset is None:
            raise ProgramError("A [DFM] section needs an ID", sectionLine)

    def _AddInterval(self, iset, tokens):
        if not tokens or not tokens[0] or not tokens[0][0].isalpha():
            iset.AddLegacyInterval(tokens)
            return
        # Paradigm name, Dark or Lit, 12 thresholds, minutes.
        paradigm = self.theParadigms.get(tokens[0].lower())
        if paradigm is None:
            raise ValueError("No Paradigm named '{}'".format(tokens[0]))
        if len(tokens) != 15:
            raise ValueError("An Interval line is: Paradigm, Dark or Lit, 12 thresholds, minutes ({} values found, 15 expected)".format(len(tokens)))
        dark = tokens[1].lower()
        if dark not in ("dark", "lit"):
            raise ValueError("The second Interval value must be Dark or Lit, not '{}'".format(tokens[1]))
        thresholds = []
        for t in tokens[2:14]:
            if t.lower() == "on":
                thresholds.append(Instruction.ON)
            elif t.lower() == "off":
                thresholds.append(Instruction.OFF)
            else:
                value = int(t) if t.lstrip("-").isdigit() else None
                if value is None or not 1 <= value <= 1023:
                    raise ValueError("Thresholds are On, Off or a signal level from 1 to 1023, not '{}'".format(t))
                thresholds.append(value)
        try:
            minutes = float(tokens[14])
        except ValueError:
            raise ValueError("The Interval's last value is its length in minutes, not '{}'".format(tokens[14])) from None
        if minutes <= 0:
            raise ValueError("An Interval must last more than 0 minutes")
        iset.AddInterval(Enums.DARKSTATE.ON if dark == "dark" else Enums.DARKSTATE.OFF, paradigm, thresholds, minutes)
    #endregion

    def UpdateStartAndEndTime(self,sTime,eTime):
        if(eTime<sTime): # This is a mistake to just update start time.
            self.startTime=sTime
        else:
            self.startTime=sTime
            self.experimentDuration = eTime-sTime
    def GetProgramType(self,dfmid):
        iset=self.theInstructionSets.get(dfmid)
        return iset.instructionSetType if iset is not None else self.globalPType
    def GetLinkage(self,dfmid):
        iset=self.theInstructionSets.get(dfmid)
        return iset.linkage if iset is not None else self.globalLinkage

    def FirmwareNeeded(self,dfmid,version=None):
        """Why DFM firmware with this version tuple can't run this DFM's Intervals (empty if it
        can). Without a version, only what needs 4.0.0 is reported."""
        iset=self.theInstructionSets.get(dfmid)
        return iset.FirmwareNeeded(version) if iset is not None else []

    def GetCurrentPosition(self,dfmid):
        """(instruction, Interval index from 0, Cycle from 1) for now, or (None, None, None)."""
        if dfmid not in self.theInstructionSets:
            self.AddSimpleProgram(dfmid,self.experimentDuration)
        return self.theInstructionSets[dfmid].GetPosition(datetime.datetime.today(),self.startTime)

    def GetCurrentInstruction(self,dfmid):
        return self.GetCurrentPosition(dfmid)[0]


#region Testing
def ModuleTest():
    tmp = MCUProgram()
    with open("FLICPrograms/TestProgram1.txt",encoding="utf-8-sig") as f:
        lines = f.readlines()
    print(tmp.LoadProgram(lines,None), tmp.loadError)
    print(tmp)

if __name__=="__main__" :
    ModuleTest()
#endregion
