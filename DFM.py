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
import Event
import Instruction


class DFM:
    DFM_message = Event.Event()
    #region Initialization, etc.
    def __init__(self,id,commProtocol):
        self.ID=id     
        self.theCOMM = commProtocol
        self.currentStatusPackets = []
        self.outputFile = "DFM" + str(self.ID) + "_0.csv"
        self.outputFileIncrementor=0
        self.status = Enums.CURRENTSTATUS.UNDEFINED
        self.pastStatus = Enums.PASTSTATUS.ALLCLEAR
        self.beforeErrorStatus = Enums.CURRENTSTATUS.UNDEFINED
        self.callLimit=3
        self.theData = DataBuffer.DataBuffer()             
        self.sampleIndex=1
        self.signalBaselines=array.array("i",(0 for i in range(0,12)))        
        self.baselineSamples=0
        self.isCalculatingBaseline=False        
        self.optoLid=OptoLid.OptoLid(Enums.OPTOLIDTYPE.NONE)           
        self.currentInstruction = Instruction.DFMInstruction()
        self.isInstructionUpdateNeeded=False
        self.currentDFMErrors = DFMErrors.DFMErrors()
        self.reportedOptoFrequency=0
        self.reportedOptoPulsewidth=0
        self.reportedOptoStateCol1=0
        self.reportedOptoStateCol2=0
        self.reportedTemperature=1.0
        self.reportedHumidity=1.0
        self.reportedLUX=0
        self.reportedVoltsIn=1.0        
    #endregion
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        DFM.DFM_message.notify(tmp)        

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
        self.isCalculatingBaseline = False
    def UpdateBaseline(self):
        last = self.GetLastAnalogData(False)
        if last is None: 
            return
        for i in range(0,12):
            tmp = self.signalBaselines[i] * self.baselineSamples
            self.signalBaselines[i] = int((tmp + last[i])/(self.baselineSamples+1))
        self.baselineSamples = self.baselineSamples+1
        if(self.baselineSamples>=30):
            self.isCalculatingBaseline=False
    def BaselineDFM(self):
        self.ResetBaseline()
        self.isCalculatingBaseline = True

    #region Packet processing, etc.
    def UpdateReportedValues(self):
        self.reportedHumidity = self.currentStatusPackets[-1].humidity
        self.reportedLUX = self.currentStatusPackets[-1].lux
        self.reportedTemperature = self.currentStatusPackets[-1].temp
        self.reportedOptoFrequency = self.currentStatusPackets[-1].optoFrequency
        self.reportedOptoPulsewidth = self.currentStatusPackets[-1].optoPulseWidth
        self.reportedOptoStateCol1  = self.currentStatusPackets[-1].optoState1
        self.reportedOptoStateCol2 = self.currentStatusPackets[-1].optoState2
        self.currentDFMErrors.UpdateErrors(self.currentStatusPackets[-1].errorFlags)
        for sp in self.currentStatusPackets:
            if(sp.errorFlags!=0):
                s="({:d}) Non-zero DFM error code".format(self.ID)
                self.NewMessage(self.ID,sp.packetTime,sp.sample,s,Enums.MESSAGETYPE.WARNING)

    def ProcessPackets(self,bytesData,timeOfMeasure):                 
        if(len(bytesData)==0):
            a=Enums.PROCESSEDPACKETRESULT.NOANSWER
            return [a,a,a,a,a]
        if(len(bytesData)!=309):
            a=Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES            
            return [a,a,a,a,a]
        if(bytesData[3]!=self.ID):
            a=Enums.PROCESSEDPACKETRESULT.WRONGID
            return [a,a,a,a,a]
        self.currentStatusPackets.clear()
        results=[]
        for i in range(0,5):
            tmpPacket = StatusPacket.StatusPacket(self.sampleIndex+i)
            results.append(tmpPacket.ProcessStatusPacket(bytesData,timeOfMeasure,i))
            self.currentStatusPackets.append(tmpPacket)
        if(results[1] == Enums.PROCESSEDPACKETRESULT.OKAY):
             self.UpdateReportedValues()            
        return results
  
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
            theResult = self.ProcessPackets(tmp,timeOfMeasure)
            if(theResult[-1]==Enums.PROCESSEDPACKETRESULT.OKAY):
                break         
            print("Calling again: {:s}" + str(theResult[-1]))
            s="Calling again: {:s}".format(str(theResult[-1]))
            self.NewMessage(self.ID,datetime.datetime.today(),self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
            time.sleep(0.005)       

        for j in range(0,5):    
            isSuccess=False
            if(theResult[j] == Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Checksum error".format(self.ID)
                self.NewMessage(self.ID,self.currentStatusPackets[j].packetTime,self.currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.ERROR)                       
            elif(theResult[j] == Enums.PROCESSEDPACKETRESULT.NOANSWER):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) No answer".format(self.ID)
                self.NewMessage(self.ID,self.currentStatusPackets[j].packetTime,self.currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.ERROR)                       
            elif(theResult[j] == Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Wrong number of bytes".format(self.ID)
                self.NewMessage(self.ID,self.currentStatusPackets[j].packetTime,self.currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.ERROR)                       
            elif(theResult[j] == Enums.PROCESSEDPACKETRESULT.OKAY):
                isSuccess=True
            if isSuccess:
                if(self.theData.NewData(self.currentStatusPackets[j],saveDataToQueue)==False):
                    s="({:d}) Data queue error".format(self.ID)
                    self.NewMessage(self.ID,self.currentStatusPackets[j].packetTime,self.currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.ERROR)
                    self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                    isSuccess = False
                else:
                    self.sampleIndex = self.sampleIndex+1
                    if(self.status == Enums.CURRENTSTATUS.ERROR):
                        self.SetStatus(self.beforeErrorStatus)                  
                if(self.isCalculatingBaseline):
                    self.UpdateBaseline()
        if(isSuccess):
            self.CheckStatus()        
    #endregion

    def ResetOutputFileStuff(self):
        self.outputFileIncrementor=0
        self.outputFile="DFM" + str(self.ID) + "_0.csv"  

    def UpdateInstruction(self,instruct,useBaseline):                    
        if(instruct is self.currentInstruction):            
            return 
        else:                      
            self.currentInstruction = instruct            
            if(useBaseline):
                self.currentInstruction.AddBaselineToCurrentOptoValues(self.signalBaselines)                        
            self.isInstructionUpdateNeeded=True

    def CheckStatus(self):
        if(self.isInstructionUpdateNeeded):
            if self.theCOMM.SendInstruction(self.ID,self.currentInstruction):
                print("Instruction success!")
                self.isInstructionUpdateNeeded=False

        

   