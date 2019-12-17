

import Enums

class MCUProgram():
    def __init__(self):
         self.theInstructionSet = {}
         self.ClearProgram()         

    
    def ClearProgram():
        ddt = datetime.datetime.today()
        self.startTime = datetime.datetime(ddt.year, ddt.month, ddt.day, ddt.hour, ddt.minute, 0);
        self.experimentDuration = datetime.timedelta(minutets=1)
        self.theInstructionSets.Clear();
        self.optoFrequency = 40;
        self.optoPulseWidth= 8;
        self.optoDecay= 0;
        self.optoDelay= 0;
        self.maxTimeOn = -1;
        self.globalLidType=Enums.OPTOLIDTYPE.NONE
        self.globalPType = Enums.INSTRUCTIONSETTYPE.LINEAR
        self.autoBaseline = True
        self.isActive = False
        self.isProgramLoaded = False

    def GetEndTime():
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

## Made it up to the last property, ProgramDescription


