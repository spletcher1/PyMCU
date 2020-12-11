import datetime
import Enums
import InstructionSet
import Instruction
import Event
import Message
import array

class MCUProgram():
    Program_message = Event.Event()

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
        self.maxTimeOn = 0
        self.globalLinkage = array.array("i",[1,2,3,4,5,6,7,8,9,10,11,12])        
        self.globalPType = Enums.INSTRUCTIONSETTYPE.LINEAR
        self.autoBaseline = True
        self.isActive = False
        self.isProgramLoaded = False

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
        self.ClearProgram()
        currentSection=""
        currentDFM=-1
        try:
            for l in lines:
                l = l.strip()         
                if len(l)==0 or l[0]=="#":
                    continue
                if "[" in l and "]" in l:
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
                            elif(thesplit[0].lower().strip()=="linkage"):                              
                                self.SetLinkageFromString(thesplit[1].strip())
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
                                ti.linkage = self.globalLinkage[:]
                                ti.maxTimeOn = self.maxTimeOn                                
                                ti.instructionSetType = self.globalPType
                                self.theInstructionSets[currentDFM] = ti
                            elif(thesplit[0].lower().strip() == "linkage"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].SetLinkageFromString(thesplit[1].strip())
                            elif(thesplit[0].lower().strip() == "optodelay"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].optoDelay=int(thesplit[1].lower().strip())
                            elif(thesplit[0].lower().strip() == "optodecay"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].optoDecay=int(thesplit[1].lower().strip())
                            elif(thesplit[0].lower().strip() == "optofrequency"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].optoFrequency=int(thesplit[1].lower().strip())
                            elif(thesplit[0].lower().strip() == "optopw"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].optoPulseWidth=int(thesplit[1].lower().strip())
                            elif(thesplit[0].lower().strip() == "maxtimeon"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].maxTimeOn=int(thesplit[1].lower().strip())
                            elif(thesplit[0].lower().strip() == "programtype"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].SetProgramTypeFromString(thesplit[1].lower().strip())
                            elif(thesplit[0].lower().strip() == "interval"):
                                if(currentDFM != -1):
                                    self.theInstructionSets[currentDFM].AddInstructionFromString(thesplit[1].lower().strip())
                    elif(currentSection.lower()=="envmon"):
                        thesplit = l.split(":")
                        if(len(thesplit)==2):
                            if (thesplit[0].lower().strip() == "id"):
                                currentDFM = 99
                                ti = InstructionSet.InstructionSet()
                                ti.optoDecay = self.optoDecay
                                ti.optoDelay = self.optoDelay
                                ti.optoFrequency = self.optoFrequency
                                ti.optoPulseWidth = self.optoPulseWidth
                                ti.linkage = self.globalLinkage[:]
                                ti.maxTimeOn = self.maxTimeOn                                
                                ti.instructionSetType = self.globalPType
                                self.theInstructionSets[currentDFM] = ti     
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
            
            # Get rid of DFMs that are not in the experiment to simplify the description textbox.           
            tmp ={}
            for key in self.theInstructionSets:
                a = False
                for d in dfmList.values():
                    if d.ID == key:
                        a = True
                if a==True:
                    tmp[key]=self.theInstructionSets[key]

            self.theInstructionSets = tmp
            
            for d in dfmList.values():                
                if(d.ID in self.theInstructionSets.keys()):
                    pass
                else :
                    self.AddSimpleProgram(d.ID,self.experimentDuration)
                    ss="DFM " + str(d.ID) + " not listed in program file. Adding simple program"
                    self.NewMessage(0,datetime.datetime.today(),0,ss,Enums.MESSAGETYPE.NOTICE)   

            allIsWell=True
            for values in self.theInstructionSets.values():
                if(values.Validate())==False:
                    ss="Invalid instruction"
                    self.NewMessage(0,datetime.datetime.today(),0,ss,Enums.MESSAGETYPE.NOTICE)
                    allIsWell=False

            if(allIsWell==False):
                ss="Program load error"
                self.NewMessage(0,datetime.datetime.today(),0,ss,Enums.MESSAGETYPE.NOTICE)            
                self.isProgramLoaded = False
                self.ClearProgram()
            else:
                self.isProgramLoaded=True            

            return allIsWell
        except:
            ss="General program load failure"
            self.NewMessage(0,datetime.datetime.today(),0,ss,Enums.MESSAGETYPE.NOTICE)   
            return False      


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

