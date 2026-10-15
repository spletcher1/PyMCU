import Enums
import array
import datetime

# Limits of DFM firmware 1.0.5 (DFMV3 before 2.0.0). It has 2-byte decay, delay and max time on,
# and none of the encodings 2.0.0 hid in the pulse width, frequency and delay/max-on fields. It
# clamps or misreads those and silently runs a different rule, so they are refused for such boards.
MAX_TIME_MS_1_0_5 = 65535
NON_FEEDING_PULSE_WIDTH = 30000   # 2.0.0 marks non-feeding activation in bit 15: 32768 + width
MAX_FREQUENCY_HZ = 500            # above this, 2.0.0 reads a training count from bits 9 and up

class DFMInstruction:
    def __init__(self,darkstate=Enums.DARKSTATE.OFF,freq=40,pw=8,decay=0,delay=0,maxTime=0,dur=datetime.timedelta(minutes=180),startt=datetime.timedelta(seconds=0)):
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


    def FirmwareNeeded(self):
        """None if firmware 1.0.5 runs this Interval as written, else a short reason naming the
        firmware it needs. Firmware 2.0.0 and later run everything."""
        if(self.pulseWidth > NON_FEEDING_PULSE_WIDTH):
            return "non-feeding activation (OptoPW above 30000) needs firmware 2.0.0"
        if(self.frequency > MAX_FREQUENCY_HZ):
            return "training count (OptoFrequency above 500) needs firmware 2.0.0"
        if(self.delay > 0 and self.maxTimeOn > 0):
            return "progressive ratio (OptoDelay and MaxTimeOn both above 0) needs firmware 2.0.0"
        if(max(self.decay, self.delay, self.maxTimeOn) > MAX_TIME_MS_1_0_5):
            return "times above 65535 ms need firmware 2.0.0"
        return None

    def SetBehaviorParameters(self, freq, pw, decay, delay, maxTime):
        self.decay = decay
        self.frequency = freq
        self.pulseWidth = pw
        self.delay=delay
        self.maxTimeOn = maxTime

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
        else:
            s="Dark Off,"

        for i in self.adjustedThresholds:
            s+=str(i)+","

        s+= "F:" + str(self.frequency) +",P:" + str(self.pulseWidth) + ",D:" + str(self.decay) +",L:" + str(self.delay) + ",M:" + str(self.maxTimeOn) +","

        s+=str(self.duration.total_seconds()/60) +"min."
        return s

def ModuleTest():
    tmp=DFMInstruction()
    print(tmp)

if __name__=="__main__" :
    ModuleTest()
