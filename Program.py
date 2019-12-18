import datetime
import Enums

class MCUProgram():
    def __init__(self):
        self.theInstructionSet = {}
        self.ClearProgram()
    
    def ClearProgram(self):
        ddt = datetime.datetime.today()
        self.startTime = datetime.datetime(ddt.year, ddt.month, ddt.day, ddt.hour, ddt.minute, 0)
        self.experimentDuration = datetime.timedelta(minutes=1)
        self.theInstructionSet.clear()
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
            sortedKeys = sorted(self.theInstructionSet.keys())
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
            
            if(len(self.theInstructionSet)>0):
                s+="placeholder"
            
        else:
            if(len(self.theInstructionSet)<1):
                s="None"
            else:
                s="***ALL DFM***\n"
                s="Start Time: " + self.startTime.strftime("%m/%d/%Y %H:%M:%S")+"\n"
                s+="End Time: " + self.GetEndTime().strftime("%m/%d/%Y %H:%M:%S")+"\n"
                s+="Duration: " +  str(self.experimentDuration.total_seconds()/60) + " min\n"
                s+="OptoLid: None"
                if(self.autoBaseline):
                    s+="Yes\n"
                else :
                    s+="No\n"
                #s+=theInstructionSet[1].ToString()



        return s



def ModuleTest():
    tmp = MCUProgram()
    tmp.isProgramLoaded=True
    print(tmp.GetProgramDescription())

if __name__=="__main__" :
    ModuleTest()        

## Made it up to the last property, ProgramDescription


