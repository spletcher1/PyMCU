import Enums
import array
import datetime

class DFMInstruction:
    def __init__(self,darkstate=Enums.DARKSTATE.UNCONTROLLED,freq=40,pw=8,decay=0,delay=0,maxTime=0,dur=datetime.timedelta(minutes=180),startt=datetime.timedelta(seconds=0)):
        self.optoValues = array.array("i",(-1 for i in range(0,12)))
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

    def AddBaselineToCurrentOptoValues(self,vals):
        for i in range(0,12):
            if(self.optoValues[i]!=0 and self.optoValues[i]!=-1):
                self.optoValues[i]+=vals[i]

    def GetElapsedEnd(self):
        return self.elapsedStart + self.duration

    def __str__(self):
        if(self.theDarkState==Enums.DARKSTATE.OFF):
            s="Dark Off,"
        elif(self.theDarkState==Enums.DARKSTATE.ON):
            s="Dark On,"
        elif(self.theDarkState==Enums.DARKSTATE.UNCONTROLLED):
            s="Dark Uncontrolled,"
        
        for i in self.optoValues:
            s+=str(i)+","
        
        s+=str(self.duration.total_seconds()/60) +"min."
        return s
  
def ModuleTest():
    tmp = DFMInstruction(Enums.DARKSTATE.ON,40,8,0,0,0,datetime.timedelta(minutes=60),datetime.timedelta(seconds=1000))
    tmp.SetOptoValues(array.array("i",(10 for i in range(0,12))))
    tmp2=DFMInstruction()
    print(tmp)
    print(tmp2)

if __name__=="__main__" :
    ModuleTest()    