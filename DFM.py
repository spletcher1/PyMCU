import datetime
import UART
import StatusPacket
import Enums




class DFM:
    def __init__(self):
        self.ID=1
        self.calculatedCheckSum=0
        self.expectedCheckSum=0
        self.theUART = UART.MyUART()
        self.currentStatutPacket = StatusPacket.StatusPacket()
    def ProcessPacket(self,bytesData):
        if(len(bytesData)==0):
            return Enums.PROCESSEDPACKETRESULT.NOANSWER
        if(len(bytesData)!=65):
            return Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES
        if(bytesData[3]!=self.ID):
            return Enums.PROCESSEDPACKETRESULT.WRONGID
        self.currentStatutPacket = StatusPacket.StatusPacket()
        return self.currentStatutPacket.ProcessStatusPacket(bytesData)
    def RequestStatus(self):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=0x01
        ba[4]=0x01
        ba[5]=0x01
        ba[6]=0x01
        ba[7]=0x01
        ba[8]=0x01
        self.theUART.WriteByteArray(ba)
    def ReadValues(self):
        self.RequestStatus()
        tmp=self.theUART.Read(65)       
        return self.ProcessPacket(tmp)
    def PrintCurrentPacket(self):
        self.currentStatutPacket.ConsolePrintPacket()
    def Read(self):
        nextTime=[0,185000,385000,585000,785000]
        i=0
        while True:   
            tt = datetime.datetime.today()
            if(i==0):
                if(tt.microsecond<nextTime[i+1]):
                    tmp=self.ReadValues()        
                    if(tmp == Enums.PROCESSEDPACKETRESULT.OKAY):            
                        self.PrintCurrentPacket()  
                    else :
                        print("bad")
                    i=i+1                
            elif(tt.microsecond>nextTime[i]):  
                tmp=self.ReadValues()        
                if(tmp == Enums.PROCESSEDPACKETRESULT.OKAY):            
                    self.PrintCurrentPacket()  
                else :
                    print("bad")
                i=i+1
                if i==5:
                    i=0
            

    

        


