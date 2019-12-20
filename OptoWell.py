import threading


class OptoWell:
    def __init__(self):
        self.isLEDOn=False
        self.delay=0
        self.decay=0
        self.maxTimeOn=-1
        self.signalThreshold=0
        self.lastSignalOverThreshold=False
        self.isCurrentlyOverMaxTimeOn=False
        self.isMaxTimeTimerRunning=False
        self.maxTimeOnResetCounter=0
        self.delayTimer=threading.Timer(10000,self.DelayTimerCallback)
        self.decayTimer=threading.Timer(10000,self.DecayTimerCallback)
        self.maxTimeTimer=threading.Timer(10000,self.MaxTimerCallback)

    def DecayTimerCallback(self):
        self.isLEDOn=False
        self.CheckForMaxTimeOnReset()
        self.StopMaxTimeTimer()

    def MaxTimerCallback(self):
        self.isLEDOn = False
        self.isCurrentlyOverMaxTimeOn=True
        self.isMaxTimeTimerRunning=False
    
    def DelayTimerCallback(self):
        self.isLEDOn=True
        if(self.isMaxTimeTimerRunning==False and self.maxTimeOn>0):
            self.StartMaxTimeTimer()
        if(self.decay>0):
            self.decayTimer=threading.Timer(self.decay,self.DecayTimerCallback)
            self.decayTimer.start()
        else:
            self.decayTimer=threading.Timer(1000,self.DecayTimerCallback)
            self.decayTimer.start()
    
    def StartMaxTimeTimer(self):        
        self.maxTimeTimer=threading.Timer(self.maxTimeOn,self.MaxTimerCallback)
        self.maxTimeTimer.start()
        self.isMaxTimeTimerRunning=True

    def StopMaxTimeTimer(self):
        self.maxTimeTimer.cancel()
        self.isMaxTimeTimerRunning=False

    def CheckForMaxTimeOnReset(self):
        if(self.maxTimeOnResetCounter>4):
            self.isCurrentlyOverMaxTimeOn=False
            self.maxTimeOnResetCounter=0
        else:
            self.maxTimeOnResetCounter+=1

    def ProcessSignal(self,currentSignal):
        if(self.signalThreshold==-1):
            self.isLEDOn=False
            return
        elif(self.signalThreshold==0):
            self.isLEDOn=True
            return

        if(currentSignal>self.signalThreshold):
            if(self.delay>0):
                self.isLEDOn=False
                self.CheckForMaxTimeOnReset()
                self.delayTimer.cancel()
                self.decayTimer.cancel()
                if(self.maxTimeOn>0):
                    self.StopMaxTimeTimer()
            else:
                if(self.decay>0):
                    self.decayTimer.cancel()
                if(self.isCurrentlyOverMaxTimeOn==False):
                    self.isLEDOn=True
                    if(self.isMaxTimeTimerRunning==False and self.maxTimeOn>0):
                        self.StartMaxTimeTimer()
                else:
                    self.isLEDOn=False
            self.lastSignalOverThreshold=True
        else:
            if(self.delay>0):
                if(self.lastSignalOverThreshold):
                    self.delayTimer=threading.Timer(self.delay,self.DelayTimerCallback)
                    self.delayTimer.start()
                    self.decayTimer.cancel()
                    if(self.maxTimeOn>0):
                        self.StopMaxTimeTimer()
            else:
                if(self.decay>0):
                    if(self.lastSignalOverThreshold):
                        self.decayTimer=threading.Timer(self.decay,self.DecayTimerCallback)
                        self.decayTimer.start()
                    if(self.isLEDOn==False and self.maxTimeOn>0):
                        self.CheckForMaxTimeOnReset()
                else:
                    self.isLEDOn=False
                    if(self.maxTimeOn>0):
                        self.CheckForMaxTimeOnReset()
                        self.StopMaxTimeTimer()
            self.lastSignalOverThreshold=False
        

def ModuleTest():
    print("Module test")
    
if __name__=="__main__" :
    ModuleTest()        

        
    

        
