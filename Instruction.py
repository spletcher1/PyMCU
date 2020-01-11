import Enums
import array
import datetime

class DFMInstruction:
    def __init__(self,darkstate=Enums.DARKSTATE.UNCONTROLLED,freq=40,pw=8,decay=0,delay=0,maxTime=0,dur=datetime.timedelta(minutes=180),startt=datetime.timedelta(seconds=0)):
        self.optoValues = array.array("i",(-1 for i in range(0,12)))
        self.baseline = array.array("i",(0 for i in range(0,12)))
        self.adjustedThresholds = array.array("i",(-1 for i in range(0,12)))
        self.theDarkState=darkstate
        self.duration = dur
        self.elapsedStart = startt
        self.pulseWidth=pw
        self.frequency=freq
        self.decay=decay
        self.delay=delay
        self.maxTimeOn=maxTime                

    def SetOptoValues(self,vals):
        for i in range(0,12):
            self.optoValues[i]=vals[i]
            if(self.optoValues[i]==0):
                self.adjustedThresholds[i]=0
            elif(self.optoValues[i]==-1):
                self.adjustedThresholds[i]=-1
            else:
                self.adjustedThresholds[i]=self.baseline[i]+self.optoValues[i]

    def SetOptoValueWell(self,well,val):
        self.optoValues[well]=val
        if(self.optoValues[well]==0):
            self.adjustedThresholds[well]=0
        elif(self.optoValues[well]==-1):
            self.adjustedThresholds[well]=-1
        else:
            self.adjustedThresholds[well]=self.baseline[well]+self.optoValues[well]

    def SetBaseline(self,vals):
        for i in range(0,12):            
            self.baseline[i]=vals[i]
            if(self.optoValues[i]==0):
                self.adjustedThresholds[i]=0
            elif(self.optoValues[i]==-1):
                self.adjustedThresholds[i]=-1
            else:
                self.adjustedThresholds[i]=self.baseline[i]+self.optoValues[i]

    def ResetBaseLine(self):
        for i in range(0,12):            
                self.baseline[i]=0

    def GetElapsedEnd(self):
        return self.elapsedStart + self.duration

    def __str__(self):
        if(self.theDarkState==Enums.DARKSTATE.OFF):
            s="Dark Off,"
        elif(self.theDarkState==Enums.DARKSTATE.ON):
            s="Dark On,"
        elif(self.theDarkState==Enums.DARKSTATE.UNCONTROLLED):
            s="Dark Uncontrolled,"
        
        for i in self.adjustedThresholds:
            s+=str(i)+","
        
        s+=str(self.duration.total_seconds()/60) +"min."
        return s
  
def ModuleTest():   
    tmp=DFMInstruction()
    print(tmp)    

if __name__=="__main__" :
    ModuleTest()    