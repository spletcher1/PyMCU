import Instruction
from Enums import INSTRUCTIONSETTYPE
from Enums import OPTOLIDTYPE
from Enums import DARKSTATE
import datetime
import array



class InstructionSet:
    def __init__(self):
        self.Clear()

    def GetDuration(self):
        tmp = datetime.timedelta(seconds=0)
        for i in self.instructions:
            tmp = tmp+i.duration
        return tmp

    def _GetInstruction(self,td : datetime.timedelta):
        if(td.totalseconds()<=0):
            return None
        for i in self.instructions:
            if (td.totalseconds() > i.elapsedStart.totalseconds()) and (td.totalseconds() <= i.GetElapsedEnd().totalseconds()):
                return i
        return self.instructions[-1]
    
    def GetInstruction(self,now,startTime):
        if(len(self.instructions <=0)) : return None
        if(self.instructionSetType == INSTRUCTIONSETTYPE.LINEAR):
            return self._GetInstruction(now-startTime)
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.CIRCADIAN):
            # We are now assuming circaidan programs start at midnight
            elapsedSecondsFromMidnight = now.hour*60*60+now.minute*60+now.second
            return self._GetInstruction(datetime.timedelta(seconds=elapsedSecondsFromMidnight))
        elif(self.instructionSetType == INSTRUCTIONSETTYPE.REPEATING):
            ts = now-startTime
            lastInstruction = self.instructions[-1]
            diff = ts.totalseconds() % lastInstruction.GetElapsedEnd().totalseconds()
            return self._GetInstruction(datetime.timedelta(seconds=diff))
        else:
            return None

    def Validate(self):
        if(self.instructionSetType==INSTRUCTIONSETTYPE.CIRCADIAN):
            if(len(self.instructions)==0):
                return False
            totalSeconds = self.instructions[-1].GetElapsedEnd().totalseconds()
            if(totalSeconds!=86400):
                return False
            else:
                return True
        else:
            return True

    def AddDefaultInstructions(self):
        self.instructions.append(Instruction.DFMInstruction())

    def AddInstruction(self, instruct:Instruction.DFMInstruction):
        if(len(self.instructions)==0):
            referencedStart = datetime.timedelta(seconds=0)
        else:
            lastoi = self.instructions[-1]
            referencedStart = lastoi.GetElapsedEnd()
        tmp=Instruction.DFMInstruction(instruct.theDarkState,instruct.duration,referencedStart)
        tmp.SetOptoValues(instruct.optoValues)
        self.instructions.append()        
        return True

    def AddInstructionFromString(self,s):
        ss = s.split(",")
        if(len(ss)==14):
            if(int(ss[0]) == 0):
                ds = DARKSTATE.OFF
            elif(int(ss[0])==1):
                ds= DARKSTATE.ON
            else:
                ds=DARKSTATE.UNCONTROLLED
            if(int(ss[1])==-1):
                ov = array.array("i",(-1 for j in range(0,12)))
            else:
                ov2 = array.array("i",(-1 for jj in range(0,12)))
                for x in range(0,12):
                    ov2[x]=int(ss[x+1])
                for ii in range(0,12):
                    if(ov2[ii]>1023): 
                        ov2[ii]=-1
            dur = datetime.timedelta(seconds=(int(s[13])*60))
            tmp = Instruction.DFMInstruction(ds,dur,0)
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

    def SetLidTypeFromString(self,lt):
        if(lt.lower()=="none" or lt=="0"):
            self.lidType = OPTOLIDTYPE.NONE
        elif(lt.lower()=="one" or lt=="1"):
            self.lidType = OPTOLIDTYPE.ONECHAMBER
        elif(lt.lower()=="six" or lt=="6"):
            self.lidType = OPTOLIDTYPE.SIXCHAMBER
        elif(lt.lower()=="twelve" or lt=="12"):
            self.lidType = OPTOLIDTYPE.TWELVECHAMBER
        else:
            self.lidType = OPTOLIDTYPE.NONE                      

    def Clear(self):
        self.instructions=[]
        self.instructionSetType = INSTRUCTIONSETTYPE.LINEAR 
        self.lidType = OPTOLIDTYPE.NONE
        self.optoDelay=0
        self.optoDecay=0
        self.optoFrequency=40
        self.optoPulseWidth=8
        self.maxTimeOn = -1
            
    def __str__(self):
        s = "Porgram Type: "
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

    def ToString(self,duration,startTime):
        s="Optolid: "
        if(self.lidType==OPTOLIDTYPE.NONE):
            s+="None"
        elif(self.lidType==OPTOLIDTYPE.ONECHAMBER):
            s+="One"
        elif(self.lidType==OPTOLIDTYPE.TWELVECHAMBER):
            s+="Twelve"
        elif(self.lidType==OPTOLIDTYPE.SIXCHAMBER):
            s+="Six"            

        s+="\n"
        s+="Opto Frequency: " + str(self.optoFrequency) +"Hz"
        s+="Opto Pulsewidth: " + str(self.optoPulseWidth) + "ms"
        s+="Opto Delay: " + str(self.optoDelay) + "ms"
        s+="Opto Decay: " + str(self.optoDecay) + "ms"
        s+="Max Time On: " + str(self.maxTimeOn) + "ms"

        s += "Porgram Type: "
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
                tmp = startTime+i.elapsedStart.strftime("%m/%d/%Y %H:%M:%S")
                s+="(" + tmp +") "
                s+=str(i)+"\n"

        return s

def ModuleTest():
    tmp = InstructionSet()


if __name__=="__main__" :
    ModuleTest()    




        
