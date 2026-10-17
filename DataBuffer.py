import StatusPacket
import Enums
from collections import deque

# The records waiting to be written, kept as their finished data-file lines (about 400 bytes
# each, where a packet object is several times that). An hour of one DFM's records: the DFM
# has already dropped them, so this is all there is while the data file can't be written.
MAX_RECORDS = 18000

class DataBuffer:
    def __init__(self):
        self.maxSize=MAX_RECORDS
        self.theData = deque()
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
            self.theData.append(newStatusPacket.GetDataBufferPrintPacket())
        return True
    def PeekRecordsAsString(self):
        """Returns (lines, count) for every buffered record. The records stay buffered until
        RemoveRecords(count), so they aren't lost if writing them fails."""
        return "".join(self.theData), len(self.theData)
    def RemoveRecords(self,count):
        for _ in range(count):
            self.theData.popleft()
