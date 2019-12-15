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
    def AddChecksumTwoBytes(self, bytes):
        checksum=0
        tmp = len(bytes)
        for i in range(0,tmp-2):
            checksum=checksum+bytes[i]
        checksum = (checksum ^ 0xFFFFFFFF) + 0x01
        checksum = checksum & 0x0000FFFF
        bytes[tmp-2] = (checksum>>8) & 0xFF
        bytes[tmp-1] = (checksum) & 0xFF
    def RequestStatus(self):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=self.ID
        ba[4]=0x01
        ba[5]=0x01
        ba[6]=0x01
        ba[7]=0x01
        ba[8]=0x01
        self.theUART.WriteByteArray(ba)
    def SendOptoState(self, os1, os2):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=self.ID
        ba[4]=0x03
        ba[5]=os1
        ba[6]=os2
        self.AddChecksumTwoBytes(ba)       
        self.theUART.WriteByteArray(ba)
    def SendPulseWidth(self, pw):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=self.ID
        ba[4]=0x05
        ba[5]=(pw>>8) & 0xFF
        ba[6]= (pw & 0xFF)
        self.AddChecksumTwoBytes(ba)
        self.theUART.WriteByteArray(ba)
    def SendFrequency(self,freq):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=self.ID
        ba[4]=0x04
        ba[5]=(freq>>8) & 0xFF
        ba[6]= (freq & 0xFF)
        self.AddChecksumTwoBytes(ba)
        self.theUART.WriteByteArray(ba)
    def GoDark(self):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=self.ID
        ba[4]=0x02
        ba[5]=0x01
        ba[6]=0x01
        self.AddChecksumTwoBytes(ba)
        self.theUART.WriteByteArray(ba)      
    def ExitDark(self):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=self.ID
        ba[4]=0x02
        ba[5]=0x00
        ba[6]=0x01
        self.AddChecksumTwoBytes(ba)
        self.theUART.WriteByteArray(ba)                
    def ReadValues(self):
        self.RequestStatus()
        tmp=self.theUART.Read(65)       
        return self.ProcessPacket(tmp)
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

    def PrintCurrentPacket(self):
        self.currentStatutPacket.ConsolePrintPacket()
    def TestRead(self):
        #nextTime=[0,185000,385000,585000,785000]
        nextTime=[0,385000,785000]
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
                if i==len(nextTime):
                    i=0
    def TestRead2(self):
        command="none"
        while command.lower() != "exit" and command.lower() != "quit":
            commandLine=input('> ')
            command=""
            argument = ""
            theSplit = commandLine.split()
            if len(theSplit)==1:
                command = theSplit[0].strip()
                if command.lower() == "read":
                    tmp=self.ReadValues()                     
                    if(tmp == Enums.PROCESSEDPACKETRESULT.OKAY):            
                        self.PrintCurrentPacket()  
                    else :
                        print("bad")           
                elif command.lower()== 'dark':
                    self.GoDark()
                elif command.lower()== 'light' or command.lower()== 'remote':
                    self.ExitDark()
                elif command.lower()== 'lowfreq':
                    self.SendFrequency(0x02)                                    
                elif command.lower()== 'highfreq':
                    self.SendFrequency(40)    
                elif command.lower()== 'lightson':
                    self.SendOptoState(0x3F,0x3F)
                elif command.lower()== 'lightsoff':
                    self.SendOptoState(0x00,0x00)
                elif command.lower()== 'longpulse':
                    self.SendPulseWidth(50)
                elif command.lower()== 'shortpulse':
                    self.SendPulseWidth(2)
                elif command.lower()== 'poll1':
                    print(self.PollSlave(1))                 
                elif command.lower()== 'poll2':
                    print(self.PollSlave(2))                 
                else:
                    print("Command not recognized.")                                        
            else:
                print("Command not recognized.")    
            

    

        


