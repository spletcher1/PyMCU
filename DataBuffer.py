import StatusPacket
import Enums
from collections import deque

class DataBuffer:
    def __init__(self):
        self.maxSize=2000
        self.theData = deque(maxlen=self.maxSize)
        self.lastDataPoint = StatusPacket.StatusPacket(0,0,Enums.DFMTYPE.PLETCHERV3)
    def GetLastDataPoint(self):
        return self.lastDataPoint
    def IsFull(self):
        return (len(self.theData)>=self.maxSize)
    def ActualSize(self):
        return len(self.theData)
    def NewData(self,newStatusPacket,addToQueue=True):          
        if(self.IsFull()):
            return False                     
        self.lastDataPoint = newStatusPacket               
        if(addToQueue):
            self.theData.append(newStatusPacket)           
        return True
    def PeekRecordsAsString(self):
        """Returns (lines, count) for every buffered record. The records stay buffered until
        RemoveRecords(count), so they aren't lost if writing them fails."""
        return "".join(sdr.GetDataBufferPrintPacket() for sdr in self.theData), len(self.theData)
    def RemoveRecords(self,count):
        for _ in range(count):
            self.theData.popleft()
