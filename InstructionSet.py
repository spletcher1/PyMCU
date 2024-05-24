import Instruction
from Enums import INSTRUCTIONSETTYPE
import Enums
import datetime
import array



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
    
    def IsVersion1_5Compatible(self):
        for i in self.instructions:
            if(i.IsVersion1_5Compatible() == False):
                return False            
        return True


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

    def AddInstructionFromString(self,s):
        ss = s.split(",")
        if(len(ss)==14):
            if(int(ss[0]) == 0):
                ds = Enums.DARKSTATE.OFF
            elif(int(ss[0])==1):
                ds= Enums.DARKSTATE.ON            
            ov = array.array("i",(-1 for jj in range(0,12)))
            for x in range(0,12):
                ov[x]=int(ss[x+1])
            for ii in range(0,12):
                if(ov[ii]>1023): 
                    ov[ii]=-1          
            dur = datetime.timedelta(seconds=(float(ss[13])*60))
            # For now, we assume that freq, pw, decay, delay and maxtime are set only at the level of the whole
            # instruction set, as it was for the DFM V2 software. 
            # TODO: loosen this and make each adjustable from the program for each instruction.
            tmp = Instruction.DFMInstruction(ds,self.optoFrequency,self.optoPulseWidth,self.optoDecay,self.optoDelay,self.maxTimeOn,dur,0)
            tmp.SetOptoValues(ov)
            self.AddInstruction(tmp)
        else:
            self.RaiseError("Wrong instruction string length.")

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
    tmp2 = Instruction.DFMInstruction(dur=datetime.timedelta(minutes=60))
    tmp.AddInstruction(tmp2)
    tmp.AddInstructionFromString("1,10,11,12,13,14,15,16,17,18,19,20,21,30")
    tmp.SetProgramTypeFromString("circadian")
    tmp.SetLinkageFromString("1,2,3,1,5,6,7,1,9,10,1,12")
    print(tmp.ToString(datetime.timedelta(minutes=200),datetime.datetime.today()-datetime.timedelta(minutes=200)))
    


if __name__=="__main__" :
    ModuleTest()    
#endregion



        
