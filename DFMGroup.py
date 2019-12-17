import DFM
import COMM
import time
import Enums
import datetime
import threading

class DFMGroup:
    def __init__(self,commProtocol):
        self.theDFMs = []
        self.stopReadingSignal = False
        self.stopRecordingSignal = False
        self.longestQueue = 0
        self.isWriting = False
        self.isReading = False
        self.currentOutputDirector = ""
        self.theCOMM = commProtocol
    def ClearDFMList(self):
        self.theDFMs.clear()
    def StopReading(self):
        if len(self.theDFMs)==0:
            return
        if(self.isWriting):
            self.stopRecordingSignal = True               
            time.sleep(0.01)
        self.stopReadingSignal = True
        time.sleep(0.01)
        self.isReading = False
        self.ClearDFMList()
  
    def FindDFMs(self):
        self.StopReading()
        for i in range(1,3):
            if(self.theCOMM.PollSlave(i)):
                self.theDFMs.append(DFM.DFM(i,self.theCOMM))
            time.sleep(0.01)
    def StartReading(self):
        if(len(self.theDFMs)==0): 
            return
        for d in self.theDFMs:
            d.SetStatus(Enums.CURRENTSTATUS.READING)
        readThread = threading.Thread(target=self.ReadWorker)
        readThread.start()

    def ReadWorker(self):
        #nextTime=[0,185000,385000,585000,785000]
        nextTime=[0,385000,785000]
        counter=0
        indexer=0
        while True:   
            tt = datetime.datetime.today()
            if(indexer==0):
                if(tt.microsecond<nextTime[indexer+1]):
                    for d in self.theDFMs:
                        d.ReadValues()                           
                        print("read")    
                    counter=counter+1
                    indexer=indexer+1                
            elif(tt.microsecond>nextTime[indexer]):  
                for d in self.theDFMs:
                    d.ReadValues()                       
                    print("read")
                counter=counter+1
                indexer=indexer+1                
                if indexer==len(nextTime):
                    indexer=0
            time.sleep(0.001)
            if(self.stopReadingSignal):
                for d in self.theDFMs:
                    d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
                self.isReading = False
                self.theDFMs[0].PrintDataBuffer()
                return
            if (counter >=10):
                self.stopReadingSignal=True




