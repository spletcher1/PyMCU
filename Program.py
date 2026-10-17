import copy
import datetime
import Enums
import InstructionSet
import Event
import Message
import array

PROGRAM_TYPES = {"linear": Enums.INSTRUCTIONSETTYPE.LINEAR, "repeating": Enums.INSTRUCTIONSETTYPE.REPEATING,
                 "circadian": Enums.INSTRUCTIONSETTYPE.CIRCADIAN, "constant": Enums.INSTRUCTIONSETTYPE.CONSTANT}

def WholeMinute(t):
    """t with the seconds dropped, so a program starts at the top of a minute."""
    return t.replace(second=0, microsecond=0)

def NextMinute():
    """The start of the next minute, the earliest a program can start."""
    return WholeMinute(datetime.datetime.today() + datetime.timedelta(minutes=1))

class MCUProgram():
    Program_message = Event.Event()

    def __init__(self):
        self.theInstructionSets = {}
        self.ClearProgram()
    
    def __str__(self):        
        return self.GetProgramDescription()

    def ClearProgram(self):
        self.startTime = NextMinute()
        self.experimentDuration = datetime.timedelta(minutes=1)
        self.theInstructionSets.clear()
        # The [DFM] section with 'ID: All', for connected DFMs the file doesn't list by number.
        self.allInstructionSet = None
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
        if(t> self.startTime and t<self.GetEndTime()):
            return True
        else :
            return False
    def IsBeforeExperiment(self):
        t = datetime.datetime.today() 
        if(t< self.startTime):
            return True
        else :
            return False
    def IsAfterExperiment(self):
        t = datetime.datetime.today() 
        if(t > self.GetEndTime()):
            return True
        else :
            return False

    def GetProgramDescription(self):
        if(self.isProgramLoaded):             
            s="Start Time: " + self.startTime.strftime("%m/%d/%Y %H:%M:%S")+"\n"
            s+="End Time: " + self.GetEndTime().strftime("%m/%d/%Y %H:%M:%S")+"\n"
            s+="Duration: " +  str(self.experimentDuration.total_seconds()/60) + " min\n"
            s+="Default Linkage: "
            for i in self.globalLinkage:
                s+=str(i)+","
            s=s[:-1]
            s+="\n"
            s+="Default Opto Frequency: " + str(self.optoFrequency) +"Hz\n"
            s+="Default Opto Pulsewidth: " + str(self.optoPulseWidth) +"ms\n"
            s+="Default Opto Delay: " + str(self.optoDelay) +"ms\n"
            s+="Default Opto Decay: " + str(self.optoDecay) +"ms\n"
            s+="Default Max Time On: " + str(self.maxTimeOn) +"ms\n"
            s+="Default Program Type: "
            if(self.globalPType==Enums.INSTRUCTIONSETTYPE.LINEAR):
                s+="Linear\n"
            elif(self.globalPType==Enums.INSTRUCTIONSETTYPE.CIRCADIAN):
                s+="Circadian\n"
            elif(self.globalPType==Enums.INSTRUCTIONSETTYPE.REPEATING):
                s+="Repeating\n"
            elif(self.globalPType==Enums.INSTRUCTIONSETTYPE.CONSTANT):
                s+="Constant\n"

            s+="Baseline: "
            if(self.autoBaseline):
                s+="Yes\n"
            else :
                s+="No\n"
            
            if(len(self.theInstructionSets)>0):
                for (key, value) in sorted(self.theInstructionSets.items()):
                    s+="\n"
                    if(key==99):
                        s += "***Env Mon***\n"    
                    else:                        
                        s += "***DFM " + str(key) + "***\n"
                    s+=value.ToString(self.experimentDuration, self.startTime)          
            
        else:
            if(len(self.theInstructionSets)<1):
                s="None"
            else:
                s="***ALL DFM***\n"
                s+="Start Time: " + self.startTime.strftime("%m/%d/%Y %H:%M:%S")+"\n"
                s+="End Time: " + self.GetEndTime().strftime("%m/%d/%Y %H:%M:%S")+"\n"
                s+="Duration: " +  str(self.experimentDuration.total_seconds()/60) + " min\n"
                s+="Linkage: "
                for i in self.globalLinkage:
                    s+=str(i)+","
                s=s[:-1]
                s+="\n"
                s += "Baseline: "
                if(self.autoBaseline):
                    s+="Yes\n"
                else :
                    s+="No\n"       
                s+=self.theInstructionSets[1].__str__()
        return s

    def CreateSimpleProgram(self,starttime,dur):
        # This will create a "linear" experiment with the current begin time and duration.
        self.ClearProgram()
        self.startTime=WholeMinute(starttime)
        self.experimentDuration=dur
        for i in range(0,99):
            self.AddSimpleProgram(i,dur)
        
    def AddSimpleProgram(self,dfmid,dur):
        instruct = InstructionSet.InstructionSet()
        instruct.optoDecay = self.optoDecay
        instruct.optoDelay = self.optoDelay
        instruct.optoFrequency = self.optoFrequency
        instruct.optoPulseWidth =self.optoPulseWidth
        instruct.linkage = self.globalLinkage[:]
        instruct.maxTimeOn = self.maxTimeOn
        instruct.instructionSetType = self.globalPType
        instruct.AddSimpleInstruction(Enums.DARKSTATE.OFF,dur,datetime.timedelta(seconds=0))        
        self.theInstructionSets[dfmid]=instruct
    
    def SetLinkageFromString(self,lk):
        ss = lk.split(",")
        if(len(ss)==12):
            for x in range(0,12):
                self.globalLinkage[x]=int(ss[x])
    
    def LoadProgram(self,lines, dfmList):
        """Loads a Program file (its lines) for the connected DFMs (a dict by ID). Returns True,
        or False with the reason in loadError and as a Notice in the messages: a line that can't
        be used is named, with what it must be."""
        self.ClearProgram()
        try:
            self._ParseLines(lines)
            self._FillIn(dfmList)
            self.isProgramLoaded = True
            return True
        except InstructionSet.ProgramError as e:
            self._LoadFailed(str(e))
        except Exception as e:
            self._LoadFailed("unexpected error: {!r}".format(e))
        return False

    def _LoadFailed(self,reason):
        self.NewMessage(0,datetime.datetime.today(),0,"Problem loading program: " + reason,Enums.MESSAGETYPE.NOTICE)
        self.ClearProgram()
        self.loadError = reason

    def _NewInstructionSet(self):
        """An InstructionSet that starts from the [General] settings."""
        ti = InstructionSet.InstructionSet()
        ti.optoDecay = self.optoDecay
        ti.optoDelay = self.optoDelay
        ti.optoFrequency = self.optoFrequency
        ti.optoPulseWidth = self.optoPulseWidth
        ti.linkage = self.globalLinkage[:]
        ti.maxTimeOn = self.maxTimeOn
        ti.instructionSetType = self.globalPType
        return ti

    def _ParseLines(self,lines):
        section = ""
        current = None    # the InstructionSet of the [DFM] or [EnvMon] section being read
        for lineNumber, raw in enumerate(lines, 1):
            l = raw.strip()
            if len(l)==0 or l[0]=="#":
                continue
            if "[" in l and "]" in l:
                section = l[l.index("[")+1:l.index("]")].strip().lower()
                current = None
                continue
            key, sep, value = l.partition(":")
            if not sep:
                continue
            key, value = key.strip().lower(), value.strip()
            if(section=="general"):
                self._SetGeneral(key,value,lineNumber)
            elif(section in ("dfm","envmon")):
                if(key=="id"):
                    current = self._NewInstructionSet()
                    if(section=="dfm" and value.lower()=="all"):
                        self.allInstructionSet = current
                    else:
                        ID = 99 if section=="envmon" else InstructionSet.CheckedInt("ID",value,lineNumber,1,99)
                        self.theInstructionSets[ID] = current
                elif(current is not None):
                    self._SetDFM(current,key,value,lineNumber)

    def _SetGeneral(self,key,value,lineNumber):
        if(key=="expdurationmin"):
            self.experimentDuration = datetime.timedelta(minutes=InstructionSet.CheckedInt("ExpDurationMin",value,lineNumber,0,100000000))
        elif(key=="optofrequency"):
            self.optoFrequency = InstructionSet.CheckedFrequency(value,lineNumber)
        elif(key=="optopw"):
            self.optoPulseWidth = InstructionSet.CheckedPulseWidth(value,lineNumber)
        elif(key=="optodecay"):
            self.optoDecay = InstructionSet.CheckedInt("OptoDecay",value,lineNumber,0,InstructionSet.MAX_TIME_MS)
        elif(key=="optodelay"):
            self.optoDelay = InstructionSet.CheckedInt("OptoDelay",value,lineNumber,0,InstructionSet.MAX_TIME_MS)
        elif(key=="maxtimeon"):
            self.maxTimeOn = InstructionSet.CheckedInt("MaxTimeOn",value,lineNumber,0,InstructionSet.MAX_TIME_MS)
        elif(key=="programtype"):
            self.globalPType = PROGRAM_TYPES.get(value.lower(),Enums.INSTRUCTIONSETTYPE.CONSTANT)
        elif(key=="linkage"):
            self.SetLinkageFromString(value)
        elif(key=="baseline"):
            self.autoBaseline = (value.lower()=="yes")
        elif(key=="starttime"):
            self.startTime = self._ParseStartTime(value,lineNumber)

    def _ParseStartTime(self,text,lineNumber):
        """'MM/DD/YYYY HH:MM:SS', or 'HH:MM:SS' for today."""
        try:
            if "/" in text:
                return datetime.datetime.strptime(text,"%m/%d/%Y %H:%M:%S")
            return datetime.datetime.combine(datetime.date.today(),datetime.datetime.strptime(text,"%H:%M:%S").time())
        except ValueError:
            raise InstructionSet.ProgramError("line {}: StartTime must be MM/DD/YYYY HH:MM:SS or HH:MM:SS, not '{}'".format(lineNumber,text))

    def _SetDFM(self,iset,key,value,lineNumber):
        if(key=="linkage"):
            iset.SetLinkageFromString(value)
        elif(key=="optodelay"):
            iset.optoDelay = InstructionSet.CheckedInt("OptoDelay",value,lineNumber,0,InstructionSet.MAX_TIME_MS)
        elif(key=="optodecay"):
            iset.optoDecay = InstructionSet.CheckedInt("OptoDecay",value,lineNumber,0,InstructionSet.MAX_TIME_MS)
        elif(key=="optofrequency"):
            iset.optoFrequency = InstructionSet.CheckedFrequency(value,lineNumber)
        elif(key=="optopw"):
            iset.optoPulseWidth = InstructionSet.CheckedPulseWidth(value,lineNumber)
        elif(key=="maxtimeon"):
            iset.maxTimeOn = InstructionSet.CheckedInt("MaxTimeOn",value,lineNumber,0,InstructionSet.MAX_TIME_MS)
        elif(key=="programtype"):
            iset.SetProgramTypeFromString(value)
        elif(key=="interval"):
            iset.AddInstructionFromString(value,lineNumber)

    def _FillIn(self,dfmList):
        """Drops DFMs that aren't connected, gives connected DFMs the file doesn't list the
        'ID: All' program or else a simple program, and checks each program's Intervals."""
        if(self.experimentDuration.total_seconds()==0):
            for iset in list(self.theInstructionSets.values()) + [self.allInstructionSet]:
                if iset is None:
                    continue
                if iset.GetDuration() > self.experimentDuration:
                    self.experimentDuration = iset.GetDuration()
        connected = {d.ID for d in dfmList.values()}
        # Get rid of DFMs that are not in the experiment to simplify the description textbox.
        self.theInstructionSets = {ID: iset for ID, iset in self.theInstructionSets.items() if ID in connected}
        for ID in sorted(connected - set(self.theInstructionSets)):
            # Not the environmental monitor, which has its own [EnvMon] section.
            if(self.allInstructionSet is not None and dfmList[ID].DFMType != Enums.DFMTYPE.ENVMONV3):
                # A copy each, as a DFM's baseline is stored in its Intervals.
                self.theInstructionSets[ID] = copy.deepcopy(self.allInstructionSet)
                continue
            InstructionSet.CheckOptoSettings(self.optoFrequency,self.optoPulseWidth,self.optoDecay,self.optoDelay,self.maxTimeOn,0)
            self.AddSimpleProgram(ID,self.experimentDuration)
            ss="DFM " + str(ID) + " not listed in program file. Adding simple program"
            self.NewMessage(0,datetime.datetime.today(),0,ss,Enums.MESSAGETYPE.NOTICE)
        for ID, iset in sorted(self.theInstructionSets.items()):
            if(iset.Validate()==False):
                raise InstructionSet.ProgramError("DFM {}: a Circadian program's Intervals must add up to 24 hours, not {:g}".format(ID,iset.GetDuration().total_seconds()/3600))

    def UpdateStartAndEndTime(self,sTime,eTime):
        if(eTime<sTime): # This is a mistake to just update start time.
            self.startTime=sTime
        else:
            self.startTime=sTime
            self.experimentDuration = eTime-sTime
    def GetProgramType(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.instructionSetType
        else:
            return self.globalPType       
    def GetOptoFrequency(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.optoFrequency
        else:
            return self.optoFrequency
    def GetOptoPulsewidth(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.optoPulseWidth
        else:
            return self.optoPulseWidth
    def GetOptoDelay(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.optoDelay
        else:
            return self.optoDelay
    def GetOptoDecay(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.optoDecay
        else:
            return self.optoDecay
    def GetMaxTimeOn(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.maxTimeOn
        else:
            return self.maxTimeOn
    def GetLinkage(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.linkage
        else:
            return self.globalLinkage

    def GetCurrentInstruction(self,dfmid):
        iset=self.theInstructionSets.get(dfmid,'None')    
        if(iset!="None"):
            return iset.GetInstruction(datetime.datetime.today(),self.startTime)
        else:
            self.AddSimpleProgram(dfmid,self.experimentDuration)
            return self.theInstructionSets[dfmid].GetInstruction(datetime.datetime.today(),self.startTime)

    

#region Testing
def ModuleTest():
    tmp = MCUProgram()
    #tmp.AddSimpleProgram(1,datetime.timedelta(minutes=120))

    f=open("TestProgram1.txt",encoding="utf-8-sig")
    lines = f.readlines()
    f.close()
    print(tmp.LoadProgram(lines,None))
    tmp.isProgramLoaded=True
    print(tmp)
    

    

if __name__=="__main__" :
    ModuleTest()        
#endregion

