import Enums

class DFMErrors:
    """Tracks each bit of a DFM's error byte as never, currently or previously set."""
    def __init__(self):
        self.ClearErrors()

    def GetI2CErrorStatus(self):
        return self.currentErrorStatuses[0]
    def GetOERRErrorStatus(self):
        return self.currentErrorStatuses[1]
    def GetPacketErrorStatus(self):
        return self.currentErrorStatuses[2]
    def Getsi7021ErrorStatus(self):
        return self.currentErrorStatuses[3]
    def GetTSL2591ErrorStatus(self):
        return self.currentErrorStatuses[4]
    def GetFERRErrorStatus(self):
        return self.currentErrorStatuses[5]
    def GetInterruptErrorStatus(self):
        return self.currentErrorStatuses[6]
    def GetMiscErrorStatus(self):
        return self.currentErrorStatuses[7]

    def ClearErrors(self):
        self.currentErrorByte=0x00
        self.currentErrorStatuses=[Enums.REPORTEDERRORSTATUS.NEVER]*8

    def UpdateErrors(self,errorByte):
        self.currentErrorByte=errorByte
        for bit in range(0,8):
            if(errorByte & (1<<bit)):
                self.currentErrorStatuses[bit]=Enums.REPORTEDERRORSTATUS.CURRENT
            elif self.currentErrorStatuses[bit]==Enums.REPORTEDERRORSTATUS.CURRENT:
                self.currentErrorStatuses[bit]=Enums.REPORTEDERRORSTATUS.PAST
