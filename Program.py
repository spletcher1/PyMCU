import datetime
import Enums
import InstructionSet
import Instruction

class MCUProgram():
    def __init__(self):
        self.theInstructionSets = {}
        self.ClearProgram()
    
    def __str__(self):        
        return self.GetProgramDescription()

    def ClearProgram(self):
        ddt = datetime.datetime.today()
        self.startTime = datetime.datetime(ddt.year, ddt.month, ddt.day, ddt.hour, ddt.minute, 0)
        self.experimentDuration = datetime.timedelta(minutes=1)
        self.theInstructionSets.clear()
        self.optoFrequency = 40
        self.optoPulseWidth= 8
        self.optoDecay= 0
        self.optoDelay= 0
        self.maxTimeOn = -1
        self.globalLidType=Enums.OPTOLIDTYPE.NONE
        self.globalPType = Enums.INSTRUCTIONSETTYPE.LINEAR
        self.autoBaseline = True
        self.isActive = False
        self.isProgramLoaded = False
    def RaiseError(self, s):
        print(s)
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
            s+="Default OptoLid: "
            if self.globalLidType==Enums.OPTOLIDTYPE.NONE:
                s+="None\n"
            elif self.globalLidType == Enums.OPTOLIDTYPE.ONECHAMBER:
                s+="One\n"
            elif self.globalLidType == Enums.OPTOLIDTYPE.SIXCHAMBER:
                s+="Six\n"
            elif self.globalLidType == Enums.OPTOLIDTYPE.TWELVECHAMBER:
                s+="Twelve\n"
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
                    s += "***DFM " + str(key) + "***\n"
                    s+=value.ToString(self.experimentDuration, self.startTime)
            
        else:
            if(len(self.theInstructionSets)<1):
                s="None"
            else:
                s="***ALL DFM***\n"
                s="Start Time: " + self.startTime.strftime("%m/%d/%Y %H:%M:%S")+"\n"
                s+="End Time: " + self.GetEndTime().strftime("%m/%d/%Y %H:%M:%S")+"\n"
                s+="Duration: " +  str(self.experimentDuration.total_seconds()/60) + " min\n"
                s+="OptoLid: None\n"
                s += "Baseline: "
                if(self.autoBaseline):
                    s+="Yes\n"
                else :
                    s+="No\n"
                s+=self.theInstructionSets[0].__str__()
        return s

    def CreateSimpleProgram(self,starttime,dur):
        # This will create a "linear" experiment with uncontrolled Opto with the current begin time and duration.
        self.ClearProgram()
        self.startTime=starttime
        self.experimentDuration=dur
        for i in range(0,16):
            self.AddSimpleProgram(i,dur)
        
    def AddSimpleProgram(self,dfmid,dur):
        instruct = InstructionSet.InstructionSet()
        instruct.optoDecay = self.optoDecay
        instruct.optoDelay = self.optoDelay
        instruct.optoFrequency = self.optoFrequency
        instruct.optoPulseWidth =self.optoPulseWidth
        instruct.maxTimeOn = self.maxTimeOn
        instruct.lidType = self.globalLidType
        instruct.instructionSetType = self.globalPType
        tmp = Instruction.DFMInstruction(Enums.DARKSTATE.UNCONTROLLED,dur,datetime.timedelta(seconds=0))
        instruct.AddInstruction(tmp)
        self.theInstructionSets[dfmid]=instruct

    def LoadProgram(self,lines):        
        currentSection=""
        currentDFM=-1
        for l in lines:
            l = l.strip()         
            if len(l)==0 or l[0]=="#":
                continue
            if l[0]=="[" and "]" in l:
                currentSection = l[l.index("[")+1:l.index("]")]
            else:
                if(currentSection.lower()=="general"):
                    thesplit = l.split(":")                    
                    if(len(thesplit)>2):
                        thesplit[1]+=":" + thesplit[2] + ":" + thesplit[3]
                    if(len(thesplit)>=2):
                        if(thesplit[0].lower().strip()=="expdurationmin"):
                            self.experimentDuration = datetime.timedelta(minutes=int(thesplit[1].strip()))
                        elif(thesplit[0].lower().strip()=="optofrequency"):
                            self.optoFrequency = int(thesplit[1].strip())
                        elif(thesplit[0].lower().strip()=="optopw"):
                            self.optoPulseWidth = int(thesplit[1].strip())
                        elif(thesplit[0].lower().strip()=="optodecay"):
                            self.optoDecay = int(thesplit[1].strip())
                        elif(thesplit[0].lower().strip()=="optodelay"):
                            self.optoDelay = int(thesplit[1].strip())
                        elif(thesplit[0].lower().strip()=="maxtimeon"):
                            self.maxTimeOn = int(thesplit[1].strip())
                        elif(thesplit[0].lower().strip()=="programtype"):
                            pt=thesplit[1].strip().lower()
                            if(pt.lower()=="linear"):
                                self.globalPType = Enums.INSTRUCTIONSETTYPE.LINEAR
                            elif(pt.lower()=="repeating"):
                                self.globalPType = Enums.INSTRUCTIONSETTYPE.REPEATING
                            elif(pt.lower()=="circadian"):
                                self.globalPType = Enums.INSTRUCTIONSETTYPE.CIRCADIAN
                            elif(pt.lower()=="constant"):
                                self.globalPType = Enums.INSTRUCTIONSETTYPE.CONSTANT
                            else:
                                self.globalPType = Enums.INSTRUCTIONSETTYPE.CONSTANT
                        elif(thesplit[0].lower().strip()=="optolid"):
                            lt=thesplit[1].strip().lower()
                            if(lt.lower()=="none" or lt=="0"):
                                self.globalLidType = Enums.OPTOLIDTYPE.NONE
                            elif(lt.lower()=="one" or lt=="1"):
                                self.globalLidType = Enums.OPTOLIDTYPE.ONECHAMBER
                            elif(lt.lower()=="six" or lt=="6"):
                                self.globalLidType = Enums.OPTOLIDTYPE.SIXCHAMBER
                            elif(lt.lower()=="twelve" or lt=="12"):
                                self.globalLidType = Enums.OPTOLIDTYPE.TWELVECHAMBER
                            else:
                                self.globalLidType = Enums.OPTOLIDTYPE.NONE        
                        elif(thesplit[0].lower().strip()=="baseline"):
                            if(thesplit[1].strip().lower()=="yes"):
                                 self.autoBaseline=True
                            else:
                                self.autoBaseline=False
                        elif(thesplit[0].lower().strip()=="starttime"):
                            st=thesplit[1].lower().strip()
                            if "/" in st: # Assume the date is as MM/DD/YYYY HH:MM:SS
                                self.startTime = datetime.datetime.strptime(st,"%m/%d/%Y %H:%M:%S")
                            else:
                                tmp = datetime.datetime.today().strftime("%m/%d/%Y") + " " + st
                                self.startTime = datetime.datetime.strptime(tmp,"%m/%d/%Y %H:%M:%S")
                elif(currentSection.lower()=="dfm"):
                    thesplit = l.split(":")
                    if(len(thesplit)==2):
                        if (thesplit[0].lower().strip() == "id"):
                            currentDFM = int(thesplit[1].strip())
                            ti = InstructionSet.InstructionSet()
                            ti.optoDecay = self.optoDecay
                            ti.optoDelay = self.optoDelay
                            ti.optoFrequency = self.optoFrequency
                            ti.optoPulseWidth = self.optoPulseWidth
                            ti.maxTimeOn = self.maxTimeOn
                            ti.lidType = self.globalLidType
                            ti.instructionSetType = self.globalPType
                            self.theInstructionSets[currentDFM] = ti
                        elif(thesplit[0].lower().strip() == "optolid"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].SetLidTypeFromString(thesplit[1].lower().strip())
                        elif(thesplit[0].lower().strip() == "optodelay"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].optoDelay=thesplit[1].lower().strip()
                        elif(thesplit[0].lower().strip() == "optodecay"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].optoDecay=thesplit[1].lower().strip()
                        elif(thesplit[0].lower().strip() == "optofrequency"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].optoFrequency=thesplit[1].lower().strip()
                        elif(thesplit[0].lower().strip() == "optopw"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].optoPulseWidth=thesplit[1].lower().strip()
                        elif(thesplit[0].lower().strip() == "maxtimeon"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].maxTimeOn=thesplit[1].lower().strip()
                        elif(thesplit[0].lower().strip() == "programtype"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].SetProgramTypeFromString(thesplit[1].lower().strip())
                        elif(thesplit[0].lower().strip() == "interval"):
                            if(currentDFM != -1):
                                self.theInstructionSets[currentDFM].AddInstructionFromString(thesplit[1].lower().strip())
        if(self.experimentDuration.total_seconds()==0):
            for key in self.theInstructionSets:
                if self.theInstructionSets[key].GetDuration() > self.experimentDuration:
                    self.experimentDuration = self.theInstructionSets[key].GetDuration()
        
        allIsWell=True
        for values in self.theInstructionSets.values():
            if(values.Validate())==False:
                self.RaiseError("Intructionset not valid.")
                allIsWell=False

        if(allIsWell==False):
            self.RaiseError("Program load problem.")
            self.isProgramLoaded = False
            self.ClearProgram()
        else:
            self.isProgramLoaded=True

        return allIsWell
        






def ModuleTest():
    tmp = MCUProgram()
    #tmp.isProgramLoaded=False
    f=open("TestProgram1.txt")
    lines = f.readlines()
    f.close()
    tmp.LoadProgram(lines)
    print(tmp)
    

if __name__=="__main__" :
    ModuleTest()        

## Made it up to the last property, ProgramDescription


