import datetime
import UART
import StatusPacket
import Enums
import time
import DataBuffer

class DFM:
    #region Initialization, etc.
    def __init__(self):
        self.ID=1
        self.calculatedCheckSum=0
        self.expectedCheckSum=0
        self.theUART = UART.MyUART()
        self.currentStatutPacket = StatusPacket.StatusPacket(0)
        self.outputFile = "DFM" + str(self.ID) + "_0.csv"
        self.outputFileIncrementor=0
        self.status = Enums.CURRENTSTATUS.UNDEFINED
        self.pastStatus = Enums.PASTSTATUS.ALLCLEAR
        self.beforeErrorStatus = Enums.CURRENTSTATUS.UNDEFINED
        self.callLimit=3
        self.theData = DataBuffer.DataBuffer()
        self.isWriting = True
        self.sampleIndex=1
    #endregion
    #region Packet processing, etc.
    def ProcessPacket(self,bytesData):           
        if(len(bytesData)==0):
            return Enums.PROCESSEDPACKETRESULT.NOANSWER
        if(len(bytesData)!=65):
            return Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES
        if(bytesData[3]!=self.ID):
            return Enums.PROCESSEDPACKETRESULT.WRONGID
        self.currentStatutPacket = StatusPacket.StatusPacket(self.sampleIndex)
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
    #endregion
    #region DFM Commands
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
    def RaiseError(self, s):
        print(s)
    def SetStatus(self, newStatus):
        if(newStatus != self.status):
            if(newStatus == Enums.CURRENTSTATUS.ERROR):
                self.beforeErrorStatus = self.status
                self.pastStatus = Enums.PASTSTATUS.PASTERROR
            self.status = newStatus
    def ReadValues(self):
        theResult = Enums.PROCESSEDPACKETRESULT.OKAY                        
        for i in range(0,self.callLimit) :
            self.RequestStatus()
            tmp=self.theUART.Read(65)              
            theResult = self.ProcessPacket(tmp)
            if(theResult==Enums.PROCESSEDPACKETRESULT.OKAY):
                break
            time.sleep(0.005)       
        isSuccess=False
        if(theResult == Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR):
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
            s="({:d}) Checksum error.".format(self.ID)
            self.RaiseError(s)
        elif(theResult == Enums.PROCESSEDPACKETRESULT.NOANSWER):
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
            s="({:d}) No answer.".format(self.ID)
            self.RaiseError(s)
        elif(theResult == Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES):
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
            s="({:d}) Wrong number of bytes.".format(self.ID)
            self.RaiseError(s)
        elif(theResult == Enums.PROCESSEDPACKETRESULT.OKAY):
            isSuccess=True
        if isSuccess:
            if(self.theData.NewData(self.currentStatutPacket,self.isWriting)==False):
                s="({:d}) Data queue error.".format(self.ID)
                self.RaiseError(s)
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                isSuccess = False
            else:
                self.sampleIndex = self.sampleIndex+1
                if(self.status == Enums.CURRENTSTATUS.ERROR):
                    self.SetStatus(self.beforeErrorStatus)
                
        return isSuccess
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
    #endregion
    #region Testing Code
    def PrintCurrentPacket(self):
        print(self.currentStatutPacket.GetDataBufferPrintPacket())
    def PrintDataBuffer(self):
        print(self.theData.PullAllRecordsAsString())
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
            theSplit = commandLine.split()
            if len(theSplit)==1:
                command = theSplit[0].strip()
                if command.lower() == "read":
                    tmp=self.ReadValues()                     
                    if(tmp):            
                        self.PrintCurrentPacket()  
                    else :
                        print("bad")       
                elif command.lower()== 'pull':
                    self.PrintDataBuffer()    
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
                elif command.lower()== 'quit' or command.lower=='exit':    
                    print("Done")           
                else:
                    print("Command not recognized.")                                        
            else:
                print("Command not recognized.")    
    #endregion

    

        


