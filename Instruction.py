import array
import datetime

import Enums
import Paradigm

# Threshold values that set a Well On or Off regardless of the Paradigm.
ON = 0
OFF = -1


def ThresholdText(value):
    return "On" if value == ON else "Off" if value == OFF else str(value)


class DFMInstruction:
    """One Interval of a DFM's Program: dark running, the Paradigm, the Wells' thresholds and how
    long it lasts."""
    def __init__(self,darkstate=Enums.DARKSTATE.OFF,paradigm=None,dur=datetime.timedelta(minutes=180),startt=datetime.timedelta(seconds=0)):
        self.paradigm = paradigm if paradigm is not None else Paradigm.Paradigm.Idle()
        self.optoValues = array.array("i",(OFF for i in range(0,12)))
        self.baseline = array.array("i",(0 for i in range(0,12)))
        self.adjustedThresholds = array.array("i",(OFF for i in range(0,12)))
        self.theDarkState=darkstate
        self.duration = dur
        self.elapsedStart = startt

    #region Old settings, for DFM firmware before 4.0.0 and V2 DFMs
    @property
    def frequency(self):
        return self.paradigm.frequency

    @property
    def pulseWidth(self):
        return self.paradigm.pulseWidth

    @property
    def decay(self):
        return self.paradigm.LegacyFields()[2]

    @property
    def delay(self):
        return self.paradigm.LegacyFields()[3]

    @property
    def maxTimeOn(self):
        return self.paradigm.LegacyFields()[4]

    def IsVersion1_5Compatible(self):
        # Firmware 1.5 takes 2-byte decay, delay and max time on.
        return all(value>>16 == 0 for value in self.paradigm.LegacyFields()[2:])
    #endregion

    def SetOptoValues(self,vals):
        for i in range(0,12):
            self.SetOptoValueWell(i,vals[i])

    def SetOptoValueWell(self,well,val):
        self.optoValues[well]=val
        if(val==ON or val==OFF):
            self.adjustedThresholds[well]=val
        else:
            self.adjustedThresholds[well]=self.baseline[well]+val

    def SetBaseline(self,vals):
        for i in range(0,12):
            self.baseline[i]=vals[i]
        self.SetOptoValues(self.optoValues)

    def ResetBaseLine(self):
        for i in range(0,12):
                self.baseline[i]=0

    def GetElapsedEnd(self):
        return self.elapsedStart + self.duration

    def __str__(self):
        s = "Dark, " if self.theDarkState==Enums.DARKSTATE.ON else "Lit, "
        s += self.paradigm.name + ", "
        s += ",".join(ThresholdText(i) for i in self.adjustedThresholds) + ", "
        s += "{:g} min".format(self.duration.total_seconds()/60)
        return s

def ModuleTest():
    tmp=DFMInstruction()
    print(tmp)

if __name__=="__main__" :
    ModuleTest()
