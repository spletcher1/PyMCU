import datetime
import COMM
import StatusPacket
import Enums
import time
import DataBuffer
import array
import threading
import OptoLid
import DFMErrors
import MessagesList
import Message


class DFM:
    #region Initialization, etc.
    def __init__(self,id,commProtocol):
        self.ID=id     
        self.theCOMM = commProtocol
        self.currentStatusPacket = StatusPacket.StatusPacket(0)
        self.outputFile = "DFM" + str(self.ID) + "_0.csv"
        self.outputFileIncrementor=0
        self.status = Enums.CURRENTSTATUS.UNDEFINED
        self.pastStatus = Enums.PASTSTATUS.ALLCLEAR
        self.beforeErrorStatus = Enums.CURRENTSTATUS.UNDEFINED
        self.callLimit=3
        self.theData = DataBuffer.DataBuffer()             
        self.sampleIndex=1
        self.signalBaselines=array.array("i",(0 for i in range(0,12)))
        self.signalThresholds=array.array("i",(-1 for i in range(0,12)))
        self.baselineSamples=0
        self.isCalculatingBaseline=False        
        self.optoLid=OptoLid.OptoLid(Enums.OPTOLIDTYPE.NONE)       
        self.optoDecay=0
        self.optoFrequency=40
        self.optoPulsewidth=8
        self.optoDelay=0
        self.maxTimeOn=-1
        self.isInDark=False
        self.hasFrequencyChanged=False 
        self.hasPWChanged=False
        self.currentDFMErrors = DFMErrors.DFMErrors()
        self.reportedOptoFrequency=0
        self.reportedOptoPulsewidth=0
        self.reportedOptoStateCol1=0
        self.reportedOptoStateCol2=0
        self.reportedTemperature=1.0
        self.reportedHumidity=1.0
        self.reportedLUX=0
        self.reportedVoltsIn=1.0
        self.theMessageList = MessagesList.MessageList()
    #endregion
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        self.theMessageList.AddMessage(tmp)     

    #region Property-like getters and setters
    def GetDFMName(self):
        return "DFM "+str(self.ID)
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
    def UpdateReportedValues(self):
        self.reportedHumidity = self.currentStatusPacket.humidity
        self.reportedLUX = self.currentStatusPacket.lux
        self.reportedTemperature = self.currentStatusPacket.temp
        self.reportedOptoFrequency = self.currentStatusPacket.optoFrequency
        self.reportedOptoPulsewidth = self.currentStatusPacket.optoPulseWidth
        self.reportedOptoStateCol1  = self.currentStatusPacket.optoState1
        self.reportedOptoStateCol2 = self.currentStatusPacket.optoState2
        self.currentDFMErrors.UpdateErrors(self.currentStatusPacket.errorFlags)


    def ProcessPacket(self,bytesData,timeOfMeasure):           
        if(len(bytesData)==0):
            return Enums.PROCESSEDPACKETRESULT.NOANSWER
        if(len(bytesData)!=65):
            return Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES
        if(bytesData[3]!=self.ID):
            return Enums.PROCESSEDPACKETRESULT.WRONGID
        self.currentStatusPacket = StatusPacket.StatusPacket(self.sampleIndex)
        tmp = self.currentStatusPacket.ProcessStatusPacket(bytesData,timeOfMeasure)
        if(tmp == Enums.PROCESSEDPACKETRESULT.OKAY):
            self.UpdateReportedValues()
        return tmp        
    def SetTargetOptoFrequency(self,target):
        if(target!=self.optoFrequency):
            self.optoFrequency=target
            self.hasFrequencyChanged=True
    def SetTargetOptoPW(self,target):
        if(target!=self.optoPulsewidth):
            self.optoPulsewidth=target
            self.hasPWChanged=True
    #endregion
    #     
    #region DFM Commands                 
    def IncrementOutputFile(self):
        self.outputFileIncrementor+=1
        self.outputFile="DFM" + str(self.ID) + "_"+str(self.outputFileIncrementor)+".csv"
    def SetStatus(self, newStatus):
        if(newStatus != self.status):
            if(newStatus == Enums.CURRENTSTATUS.ERROR):
                self.beforeErrorStatus = self.status
                self.pastStatus = Enums.PASTSTATUS.PASTERROR
            self.status = newStatus
    def ReadValues(self,timeOfMeasure,saveDataToQueue):
        theResult = Enums.PROCESSEDPACKETRESULT.OKAY                        
        for _ in range(0,self.callLimit) :            
            tmp=self.theCOMM.GetStatusPacket(self.ID)              
            theResult = self.ProcessPacket(tmp,timeOfMeasure)
            if(theResult==Enums.PROCESSEDPACKETRESULT.OKAY):
                break
            time.sleep(0.005)       
        isSuccess=False
        if(theResult == Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR):
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
            s="({:d}) Checksum error.".format(self.ID)
            self.NewMessage(self.ID,datetime.datetime.today(),self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
        elif(theResult == Enums.PROCESSEDPACKETRESULT.NOANSWER):
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
            s="({:d}) No answer.".format(self.ID)
            self.NewMessage(self.ID,datetime.datetime.today(),self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
        elif(theResult == Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES):
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
            s="({:d}) Wrong number of bytes.".format(self.ID)
            self.NewMessage(self.ID,datetime.datetime.today(),self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
        elif(theResult == Enums.PROCESSEDPACKETRESULT.OKAY):
            isSuccess=True
        if isSuccess:
            if(self.theData.NewData(self.currentStatusPacket,saveDataToQueue)==False):
                s="({:d}) Data queue error.".format(self.ID)
                self.NewMessage(self.ID,datetime.datetime.today(),self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                isSuccess = False
            else:
                self.sampleIndex = self.sampleIndex+1
                if(self.status == Enums.CURRENTSTATUS.ERROR):
                    self.SetStatus(self.beforeErrorStatus)
                self.CheckStatus()
                
        return isSuccess
    #endregion

    def ResetOutputFileStuff(self):
        self.outputFileIncrementor=0
        self.outputFile="DFM" + str(self.ID) + "_0.csv"

    def SetAllSignalThresholds(self,thresholds):
        for i in range(0,12):
            self.signalThresholds[i]=thresholds[i]
        self.optoLid.SetAllThresholds(thresholds)

    def SetWellSignalThreshold(self,wellnum,thresh):
        if(wellnum<0 or wellnum>11): return
        self.signalThresholds[wellnum]=thresh
        self.optoLid.SetWellThreshold(wellnum,thresh)

    def SetAllSignalBaselines(self, newbaselines):
        for i in range(0,12):
            self.signalBaselines[i]=newbaselines[i]

    def CheckStatus(self):
        if(self.currentStatusPacket.darkStatus == 1 and self.isInDark == False):
            self.theCOMM.ExitDark()
        elif(self.currentStatusPacket.darkStatus==0 and self.isInDark == True):
            self.theCOMM.GoDark()

        if(self.hasFrequencyChanged or (self.reportedOptoFrequency != self.optoFrequency)):
            self.theCOMM.SendFrequency(self.optoFrequency,self.ID)
            self.hasFrequencyChanged = False

        if(self.hasPWChanged or (self.reportedOptoPulsewidth != self.optoPulsewidth)):
            self.theCOMM.SendPulseWidth(self.optoPulsewidth,self.ID)
            self.hasPWChanged = False

        self.optoLid.SetOptoState(self.GetLastAnalogData(True)) # For optolid purposes, we always used baselined data, even if it is not actually baselined.

        if((self.reportedOptoStateCol1 != self.optoLid.optoStateCol1)) or (self.reportedOptoStateCol2 != self.optoLid.optoStateCol2):
            self.theCOMM.SendOptoState(self.optoLid.optoStateCol1,self.optoLid.optoStateCol2,self.ID)
        

    #region Testing Code
    def PrintCurrentPacket(self):
        print(self.currentStatusPacket.GetDataBufferPrintPacket())
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
                    tmp=self.ReadValues(tt,True)                     
                    if(tmp == Enums.PROCESSEDPACKETRESULT.OKAY):            
                        self.PrintCurrentPacket()  
                    else :
                        print("bad")
                    i=i+1                
            elif(tt.microsecond>nextTime[i]):  
                tmp=self.ReadValues(tt,True)        
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
                    tmp=self.ReadValues(datetime.datetime.today(),True)                     
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

    

        


