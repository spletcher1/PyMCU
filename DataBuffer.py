import StatusPacket
from collections import deque

class DataBuffer:
    def __init__(self):
        self.maxSize=500
        self.theData = deque(maxlen=self.maxSize)
        self.lastDataPoint = StatusPacket.StatusPacket(0)
    def IsFull(self):
        return (len(self.theData)>=self.maxSize)
    def ActualSize(self):
        return len(self.theData)
    def NewData(self,newStatusPacket,addToQueue=True):
        if(self.IsFull()):
            return False
        print("Added")
        self.lastDataPoint = newStatusPacket
        if(addToQueue):
            self.theData.append(newStatusPacket)
        return True
    def PullAllRecordsAsString(self):
        s=""
        while self.theData:
            sdr = self.theData.popleft()            
            s+=sdr.GetDataBufferPrintPacket()
        return s
