import datetime
import COMM
import StatusPacket
import Enums
import time
import DataBuffer
import array
import threading

class DFM:
    #region Initialization, etc.
    def __init__(self,id,commProtocol):
        self.ID=id
        self.calculatedCheckSum=0
        self.expectedCheckSum=0
        self.theCOMM = commProtocol
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
        self.signalBaselines=array.array("i",(0 for i in range(0,12)))
        self.signalThresholds=array.array("i",(-1 for i in range(0,12)))
        self.baselineSamples=0
        self.isCalculatingBaseline=False
    #endregion
    #region Property-like getters and setters
    def GetLastAnalogData(self,adjustForBaseline):
        tmp = self.theData.GetLastDataPoint()
        if(tmp.sample==0):
            return None
        if(adjustForBaseline == False):
            return tmp.analogValues
        else:
            resultArray=array.array("i",(0 for i in range(0,12)))
            for i in range(0,12):
                resultArray[i]=tmp.analogValues[i]-self.signalBaselines[i]
                if(resultArray[i]<0):
                    resultArray[i]=0
            return resultArray        
    def ResetBaseline(self):
        for i in range(0,len(self.signalBaselines)):
            self.signalBaselines[i]=0
        self.baselineSamples=0
    def UpdateBaseline(self):
        last = self.GetLastAnalogData(False)
        if last is None: 
            return
        for i in range(0,12):
            tmp = self.signalBaselines[i] * self.baselineSamples
            self.signalBaselines[i] = (tmp + last[i])/(self.baselineSamples+1)
        self.baselineSamples = self.baselineSamples+1
    def BaselineDFM(self):
        self.ResetBaseline()
        self.isCalculatingBaseline = True
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
  
    #endregion
    #region DFM Commands                 
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
            tmp=self.theCOMM.GetStatusPacket(self.ID)              
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
                elif command.lower()== 'last':
                    print(self.theData.GetLastDataPoint().GetDataBufferPrintPacket())
                elif command.lower()== 'pull':
                    self.PrintDataBuffer()    
                elif command.lower()== 'dark':
                    self.theCOMM.GoDark()
                elif command.lower()== 'light':
                    self.theCOMM.ExitDark()
                elif command.lower()== 'lowfreq':
                    self.theCOMM.SendFrequency(0x02)                                    
                elif command.lower()== 'highfreq':
                    self.theCOMM.SendFrequency(40)    
                elif command.lower()== 'lightson':
                    self.theCOMM.SendOptoState(0x3F,0x3F)
                elif command.lower()== 'lightsoff':
                    self.theCOMM.SendOptoState(0x00,0x00)
                elif command.lower()== 'longpulse':
                    self.theCOMM.SendPulseWidth(50)
                elif command.lower()== 'shortpulse':
                    self.theCOMM.SendPulseWidth(2)                
                elif command.lower()== 'quit' or command.lower=='exit':    
                    print("Done")           
                else:
                    print("Command not recognized.")                                        
            else:
                print("Command not recognized.")    
    #endregion

    

        


