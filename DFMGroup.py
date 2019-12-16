import DFM
import UART
import time
import Enums
import datetime
import threading

class DFMGroup:
    def __init__(self):
        self.theDFMs = []
        self.stopReadingSignal = False
        self.stopRecordingSignal = False
        self.longestQueue = 0
        self.isWriting = False
        self.isReading = False
        self.currentOutputDirector = ""
        self.theUART = UART.MyUART()
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
    def PollSlave(self,id):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=id
        ba[4]=0x06
        ba[5]=0x01
        ba[6]=0x01
        ba[7]=0x01
        ba[8]=0x01        
        self.theUART.WriteByteArray(ba)  
        self.theUART.SetShortTimeout()    
        tmp=self.theUART.Read(1)
        self.theUART.ResetTimeout()
        if(len(tmp)==0):
            return False
        elif(tmp[0]==id) :
            return True
        else :
            return False
    def FindDFMs(self):
        self.StopReading()
        for i in range(1,17):
            if(self.PollSlave(i)):
                self.theDFMs.append(DFM.DFM(i,self.theUART))
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
                        counter=counter+1
                        print("read")                                   
                    indexer=indexer+1                
            elif(tt.microsecond>nextTime[indexer]):  
                for d in self.theDFMs:
                        d.ReadValues()   
                        counter=counter+1                      
                        print("read")
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




