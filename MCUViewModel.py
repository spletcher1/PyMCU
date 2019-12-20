import DFMGroup
import MessagesList
import Message
import datetime
import Enums
import threading
import time

class MCUViewModel:
    def __init__(self,id,commProtocol):
        self.dfmGroup = DFMGroup.DFMGroup(commProtocol)
        self.programStartTime = datetime.datetime.today()
        self.programEndTime=datetime.datetime.today() + datetime.timedelta(hours=3)
        self.updateTimer= threading.Thread(target=self.UpdateLoop)
        self.updateTimer.daemon=True
        self.killUpdateLoop=False

    def SetStartTime(self, newStartTime):        
        self.programStartTime = newStartTime
    
    def SetEndTime(self, newEndTime):
        self.programEndTime = newEndTime

    def LoadSimpleProgram(self,durationMin):
        self.dfmGroup.currentProgram.isProgramLoaded=False
        self.programEndTime = self.programStartTime + datetime.timedelta(minutes=durationMin)
        self.dfmGroup.currentProgram.CreateSimpleProgram(self.programStartTime,datetime.timedelta(minutes=durationMin))

    def ActivateCurrentProgram(self):
        self.dfmGroup.ActivateCurrentProgram()

    def StopCurrentProgram(self):
        self.StopCurrentProgram()

    def StartUpdateLoop(self):
        self.killUpdateLoop = False
        self.updateTimer.start()
    def StopUpdateLoop(self):
        self.killUpdateLoop = True
    def UpdateLoop(self):
        next_call=time.time()        
        while True:
            next_call = next_call+1            
            if(self.killUpdateLoop):
                return
            time.sleep(next_call - time.time())


def ModuleTest():
    print("Test module")


if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     