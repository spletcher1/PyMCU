import DFM
import Enums

class DFMErrors:
    def __init__(self):
        self.currentErrorByte=0x00
        self.currentErrorStatuses=[]
        for _ in range(0,8):
            self.currentErrorStatuses.append(Enums.REPORTEDERRORSTATUS.NEVER)

    def GetI2CErrorStatus(self):
        return self.currentErrorStatuses[0]

    def GetUARTErrorStatus(self):
        return self.currentErrorStatuses[1]
    def GetPacketErrorStatus(self):
        return self.currentErrorStatuses[2]
    def Getsi7021ErrorStatus(self):
        return self.currentErrorStatuses[3]
    def GetTSL2591ErrorStatus(self):
        return self.currentErrorStatuses[4]
    def GetConfigErrorStatus(self):
        return self.currentErrorStatuses[5]
    def GetTBD1ErrorStatus(self):
        return self.currentErrorStatuses[6]
    def GetTBD2ErrorStatus(self):
        return self.currentErrorStatuses[7]

    def ClearErrors(self):
        self.currentErrorByte=0x00
        for i in range(0,8):
            self.currentErrorStatuses[i]=Enums.REPORTEDERRORSTATUS.NEVER

            
    def UpdateErrors(self,errorByte):
        self.currentErrorByte=errorByte
        if((errorByte & 0x80) > 0):
            self.currentErrorStatuses[7]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[7]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[7]=Enums.REPORTEDERRORSTATUS.PAST

        if((errorByte & 0x40) > 0):
            self.currentErrorStatuses[6]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[6]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[6]=Enums.REPORTEDERRORSTATUS.PAST

        if((errorByte & 0x20) > 0):
            self.currentErrorStatuses[5]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[5]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[5]=Enums.REPORTEDERRORSTATUS.PAST

        if((errorByte & 0x10) > 0):
            self.currentErrorStatuses[4]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[4]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[4]=Enums.REPORTEDERRORSTATUS.PAST

        if((errorByte & 0x08) > 0):
            self.currentErrorStatuses[3]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[3]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[3]=Enums.REPORTEDERRORSTATUS.PAST

        if((errorByte & 0x04) > 0):
            self.currentErrorStatuses[2]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[2]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[2]=Enums.REPORTEDERRORSTATUS.PAST

        if((errorByte & 0x02) > 0):
            self.currentErrorStatuses[1]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[1]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[1]=Enums.REPORTEDERRORSTATUS.PAST

        if((errorByte & 0x01) > 0):
            self.currentErrorStatuses[0]=Enums.REPORTEDERRORSTATUS.CURRENT
        elif self.currentErrorStatuses[0]==Enums.REPORTEDERRORSTATUS.CURRENT:
            self.currentErrorStatuses[0]=Enums.REPORTEDERRORSTATUS.PAST