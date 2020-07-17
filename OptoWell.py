import Enums
import time
import threading

class OptoWell:
    def __init__(self,delay=0,decay=0,maxtimeon=0,signalthreshold=-1):
        # Values are in milliseconds
        self.delay=delay
        self.decay=decay
        self.maxTimeOn=maxtimeon
        self.signalThreshold=signalthreshold
        self.lastSignalOverThreshold=False
        self.isCurrentlyOverMaxTimeOn=False
        self.isMaxTimeTimerRunning=False
        self.maxTimeOnResetCounter=0
        self.isLEDOn=False
        self.decayTimer = None
        self.delayTimer=None
        self.maxTimeTimer=None

    def DecayTimerCallback(self):        
        self.isLEDOn=False
        self.CheckForMaxTimeOnReset()
        self.StopMaxTimeTimer()

    def MaxTimerCallback(self):
        self.isLEDOn=False
        self.isCurrentlyOverMaxTimeOn=True
        self.isMaxTimeTimerRunning=False

    def StartDecayTimer(self):                
        if self.decayTimer is not None:
            self.decayTimer.cancel()
        self.decayTimer = threading.Timer(self.decay/1000,self.DecayTimerCallback)
        self.decayTimer.start()

    def StopDecayTimer(self):         
        if self.decayTimer is not None:
            self.decayTimer.cancel()
        self.decayTimer = None

    def StartDelayTimer(self):    
        if self.delayTimer is not None:
            self.delayTimer.cancel()
        self.delayTimer = threading.Timer(self.delay/1000,self.DelayTimerCallback)
        self.delayTimer.start()

    def StopDelayTimer(self):        
        if self.delayTimer is not None:
            self.delayTimer.cancel()
        self.delayTimer = None

    def DelayTimerCallback(self):        
        self.isLEDOn=True
        if(self.isMaxTimeTimerRunning==False and self.maxTimeOn>0):
            self.StopMaxTimeTimer()
        # Assume a minimal decay time or it doesn't make sense.
        if(self.decay==0):
            self.decay=1000
        self.StartDecayTimer()
        
    def StartMaxTimeTimer(self):
        if(self.maxTimeTimer is not None):
            self.maxTimeTimer.cancel()
        self.maxTimeTimer = threading.Timer(self.maxTimeOn/1000,self.MaxTimerCallback)
        self.isMaxTimeTimerRunning = True
        self.maxTimeTimer.start()

    def StopMaxTimeTimer(self):
        if(self.maxTimeTimer is not None):
            self.maxTimeTimer.cancel()
        self.maxTimeTimer=None
        self.isMaxTimeTimerRunning = False

    def CheckForMaxTimeOnReset(self):
        self.maxTimeOnResetCounter+=1
        if(self.maxTimeOnResetCounter>4):
            self.isCurrentlyOverMaxTimeOn=False
            self.maxTimeOnResetCounter=0
        

    def ProcessSignal(self, currentSignal):
        if(self.signalThreshold == -1):
            self.isLEDOn = False
            return
        elif (self.signalThreshold==0):            
            self.isLEDOn=True
            return
           
        if(currentSignal > self.signalThreshold):
            if(self.delay>0):                
                self.isLEDOn = False
                self.CheckForMaxTimeOnReset()
                self.StopDecayTimer()
                self.StopDelayTimer()
                if(self.maxTimeOn>0):
                    self.StopMaxTimeTimer()
            else:
                if(self.decay>0):
                    self.StopDecayTimer()
                if self.isCurrentlyOverMaxTimeOn == False:
                    self.isLEDOn=True
                    if(self.isMaxTimeTimerRunning == False and self.maxTimeOn>0):
                        self.StartMaxTimeTimer()
                else:
                    self.isLEDOn=False
            self.lastSignalOverThreshold=True
        
        else:
            if(self.delay>0):                
                if(self.lastSignalOverThreshold):
                    self.StartDelayTimer()
                    self.StopDecayTimer()
                    if(self.maxTimeOn>0):
                        self.StopMaxTimeTimer()
            else:
                if(self.decay>0):
                    if(self.lastSignalOverThreshold):
                        self.StartDecayTimer()
                    if(self.isLEDOn==False and self.maxTimeOn>0):
                        self.CheckForMaxTimeOnReset()
                else:
                    self.isLEDOn=False
                    if(self.maxTimeOn>0):
                        self.CheckForMaxTimeOnReset()
                        self.StopMaxTimeTimer()
            self.lastSignalOverThreshold=False






        

        




        