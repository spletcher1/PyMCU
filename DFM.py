import datetime
import StatusPacket
import Enums
import time
import DataBuffer
import array
import threading
import DFMErrors
import MessagesList
import Message
import Event
import Instruction
import Board
import math
import OptoLid
from DataGetter import MP_Command
 
class DFM:
    DFM_message = Event.Event()    
    #region Initialization, etc.
    def __init__(self,id,dfmType,mp):
        self.MP = mp
        self.ID=id             
        self.DFMType = dfmType   
        ## Set this to 1.5 and only change if found to be needed.
        self.DFMSubType = Enums.DFMSUBTYPE.V1_5
        self.outputFile = "DFM" + str(self.ID) + "_0.csv"
        self.outputFileIncrementor=0
        self.status = Enums.CURRENTSTATUS.UNDEFINED
        self.pastStatus = Enums.PASTSTATUS.ALLCLEAR        
        self.theData = DataBuffer.DataBuffer()             
        self.sampleIndex=1
        self.lastDFMIndex=0
        self.signalBaselines=array.array("i",(0 for i in range(0,12)))      
        self.currentLinkage = array.array("i",[1,2,3,4,5,6,7,8,9,10,11,12])    
        self.baselineSamples=0
        self.isCalculatingBaseline=False                   
        self.currentInstruction = Instruction.DFMInstruction()
        self.isInstructionUpdateNeeded=False
        self.isBufferResetNeeded=False
        self.isVersionGetNeeded = True
        self.isLinkageSetNeeded=False
        self.currentDFMErrors = DFMErrors.DFMErrors()
        self.reportedOptoFrequency=0
        self.reportedOptoPulsewidth=0
        self.reportedOptoStateCol1=0
        self.reportedOptoStateCol2=0
        self.reportedTemperature=1.0
        self.reportedDarkState = Enums.DARKSTATE.OFF
        self.reportedHumidity=1.0
        self.reportedLUX=0
        self.reportedVoltsIn=1.0                        
        self.firmwareVersion="0.0.0"
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV2):
            self.theOptoLid = OptoLid.OptoLid()       

    def __str__(self):
        return "DFM " + str(self.ID)

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)        
        DFM.DFM_message.notify(tmp)        
    #endregion
  
    #region Property-like getters and setters
    def SetLinkage(self,links):
        self.currentLinkage = links
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV2):
            self.theOptoLid.SetLinkage(self.currentLinkage)
        self.isLinkageSetNeeded = True

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

    def SetIdleStatus(self):
        ## Idle is opto off, dark running as its has been, and default other parameters.
        self.currentInstruction = Instruction.DFMInstruction()
        self.isInstructionUpdateNeeded=True

    def SetOutputsOn(self):
        self.currentInstruction = Instruction.DFMInstruction()
        self.currentInstruction.SetOptoValues([0]*12)
        self.isInstructionUpdateNeeded=True        

    def SetOutputsOff(self):       
        self.currentInstruction = Instruction.DFMInstruction()        
        self.isInstructionUpdateNeeded=True
        
    def SetStatus(self, newStatus):
        if(newStatus != self.status):            
            if(newStatus == Enums.CURRENTSTATUS.ERROR or newStatus == Enums.CURRENTSTATUS.MISSING):               
                self.pastStatus = Enums.PASTSTATUS.PASTERROR                     
            self.status = newStatus
    #endregion
  
    #region Baselining
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
        if (self.baselineSamples>=10):
            self.isCalculatingBaseline=False              
    def BaselineDFM(self):
        self.ResetBaseline()
        self.isCalculatingBaseline = True
    #endregion

    #region Packet processing, reading, writing, file methods.  
    def UpdateReportedValues(self, currentStatusPackets):
        self.reportedHumidity = currentStatusPackets[-1].humidity
        self.reportedLUX = currentStatusPackets[-1].lux
        self.reportedTemperature = currentStatusPackets[-1].temp
        self.reportedOptoFrequency = currentStatusPackets[-1].optoFrequency
        self.reportedOptoPulsewidth = currentStatusPackets[-1].optoPulseWidth
        self.reportedOptoStateCol1  = currentStatusPackets[-1].optoState1
        self.reportedOptoStateCol2 = currentStatusPackets[-1].optoState2       
        self.reportedVoltsIn = currentStatusPackets[-1].voltsIn
        
        
        if(currentStatusPackets[-1].darkStatus==0):
            self.reportedDarkState = Enums.DARKSTATE.OFF
        else:
            self.reportedDarkState = Enums.DARKSTATE.ON

        for sp in currentStatusPackets:
            if(sp.processResult == Enums.PROCESSEDPACKETRESULT.OKAY):
                self.currentDFMErrors.UpdateErrors(sp.errorFlags)
                if(sp.errorFlags!=0):
                    s="DFM code: {:02X}".format(sp.errorFlags)
                    self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,s,Enums.MESSAGETYPE.NOTICE)

        ## TODO: Decide whether to incorporate this (and more) "closed loop" behavior. 
        ##if self.isInstructionUpdateNeeded:
        ##    return # This is here to avoid loop 
        ##tmpisInstructionUpdateNeeded=False
        ##if(self.currentInstruction.frequency != self.reportedOptoFrequency):
        ##    tmpisInstructionUpdateNeeded=True
        ##elif(self.currentInstruction.pulseWidth != self.reportedOptoPulsewidth):
        ##    tmpisInstructionUpdateNeeded=True
        ##elif(self.currentInstruction.theDarkState != self.reportedDarkState):
        ##    tmpisInstructionUpdateNeeded=True
        
        ##if(tmpisInstructionUpdateNeeded):
        ##   self.isInstructionUpdateNeeded=True

    def ProcessPackets(self,currentStatusPackets,saveDataToQueue):                                  
        for j in range(0,len(currentStatusPackets)):                  
            isSuccess=False   
            if (self.DFMType == Enums.DFMTYPE.PLETCHERV3):
                theMessageType =  Enums.MESSAGETYPE.NOTICE
            else:  
                theMessageType =  Enums.MESSAGETYPE.ERROR
            if(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR):            
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Checksum mismatch".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,theMessageType)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.NOANSWER):                
                self.SetStatus(Enums.CURRENTSTATUS.MISSING)
                s="({:d}) No answer".format(self.ID)                
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,theMessageType)                                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Packet size mismatch".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,theMessageType)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.INCOMPLETEPACKET):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Incomplete packet received".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,theMessageType)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.OKAY):              
                isSuccess=True
            if isSuccess:                                                                                                                                            
                if (currentStatusPackets[j].recordIndex>0):                                                   
                    currentStatusPackets[j].sample = self.sampleIndex                                                          
                    if(self.theData.NewData(currentStatusPackets[j],saveDataToQueue)==False):     
                        s="({:d}) Data queue full".format(self.ID)
                        self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.ERROR)
                        self.SetStatus(Enums.CURRENTSTATUS.ERROR)                       
                    else:                                  
                        if(saveDataToQueue): 
                            if(self.DFMType==Enums.DFMTYPE.PLETCHERV3):
                                if(currentStatusPackets[j].recordIndex != (self.lastDFMIndex+1)):
                                    s="({:d}) Skipped index: ({:d}) ".format(currentStatusPackets[j].recordIndex,self.lastDFMIndex)
                                    #s="({:d}) Skipped index:".format(self.ID)                                
                                    self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.ERROR)
                                    self.SetStatus(Enums.CURRENTSTATUS.ERROR)  
                                self.lastDFMIndex = currentStatusPackets[j].recordIndex
                            self.sampleIndex+=1                                                       
                            self.SetStatus(Enums.CURRENTSTATUS.RECORDING)
                        else:
                            self.SetStatus(Enums.CURRENTSTATUS.READING)                                     
                    if(self.isCalculatingBaseline):                        
                        self.UpdateBaseline()
                else :
                    # It's okay now to receive these because of the fast buffer reset and call. I will not call this an error.                    
                    s="({:d}) Empty packet received".format(self.ID)
                    print(s)
                    #self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.NOTICE)                       
  
        if isSuccess:    
            self.UpdateReportedValues(currentStatusPackets) 

        self.CheckStatus()

    def ResetOutputFileStuff(self):
        self.outputFileIncrementor=0
        self.outputFile="DFM" + str(self.ID) + "_0.csv"       
    
    def IncrementOutputFile(self):
        self.outputFileIncrementor+=1
        self.outputFile="DFM" + str(self.ID) + "_"+str(self.outputFileIncrementor)+".csv"

    #endregion

    #region Updating                
 
    def UpdateInstruction(self,instruct,useBaseline):                      
        if(instruct is self.currentInstruction):            
            return 
        else:                                  
            self.currentInstruction = instruct                        
            if(useBaseline):
                self.currentInstruction.SetBaseline(self.signalBaselines)                        
            self.isInstructionUpdateNeeded=True                     
    
    def CheckStatus(self):
        if(self.DFMType == Enums.DFMTYPE.PLETCHERV3):               
            self.CheckStatusV3()
        elif(self.DFMType == Enums.DFMTYPE.PLETCHERV2):
            self.CheckStatusV2()
        else:
            pass #Sable V2 doesn't need anything here.

    def CheckStatusV2(self):    
        if self.status == Enums.CURRENTSTATUS.MISSING or self.status == Enums.CURRENTSTATUS.ERROR or self.status == Enums.CURRENTSTATUS.UNDEFINED:
            return              
        lsp = self.theData.GetLastDataPoint()   
        
        if(lsp.optoFrequency!=self.currentInstruction.frequency):     
            self.MP.SendFrequency(self.ID,self.currentInstruction.frequency)       
           
        if(lsp.optoPulseWidth!=self.currentInstruction.pulseWidth):               
            self.MP.SendPulseWidth(self.ID,self.currentInstruction.pulseWidth)
            
        if(lsp.darkStatus!=self.currentInstruction.theDarkState.value):         
            self.MP.SendDarkState(self.ID,self.currentInstruction.theDarkState.value)          
               
        if(self.isInstructionUpdateNeeded):                
            self.theOptoLid.UpdateWithInstruction(self.currentInstruction)                               
            self.isInstructionUpdateNeeded=False
        
        self.theOptoLid.SetOptoState(lsp.analogValues)                      
        if(lsp.optoState1!=self.theOptoLid.optoStateCol1 or lsp.optoState2!=self.theOptoLid.optoStateCol2):   
            self.MP.SendOptoState(self.ID,self.theOptoLid.optoStateCol1,self.theOptoLid.optoStateCol2)                 

    def CheckStatusV3(self):     
        # To avoid sending repeated instructions to missing DFM that are never acked and therefore continue to be queued and sent.
        if self.status == Enums.CURRENTSTATUS.MISSING or self.status == Enums.CURRENTSTATUS.ERROR or self.status == Enums.CURRENTSTATUS.UNDEFINED:            
            return
        if(self.isBufferResetNeeded):                  
            if(self.MP.SendBufferReset(self.ID)):                    
                self.isBufferResetNeeded=False
                self.sampleIndex=1      
                self.lastDFMIndex=0;              
            else:
                print("Buffer reset NACKed")                 
        if(self.isInstructionUpdateNeeded):      
            if(self.DFMSubType == Enums.DFMSUBTYPE.V1_5):      
                if(self.MP.SendInstructionDFMV1_5(self.ID, self.currentInstruction)):                       
                    self.isInstructionUpdateNeeded=False
                else:
                    print("Instruction update NACKed")            
            elif (self.DFMSubType == Enums.DFMSUBTYPE.V2):                              
                if(self.MP.SendInstructionDFMV2_0(self.ID, self.currentInstruction)):                       
                    self.isInstructionUpdateNeeded=False
                else:
                    print("Instruction update NACKed")      
           
        if(self.isVersionGetNeeded):
            v = self.MP.GetVersion(self.ID)
            if(v[0]==self.ID):        
                v2 = v[1].decode("utf-8")
                self.firmwareVersion = v2
                if(v2 == "2.0.0"):
                    self.DFMSubType = Enums.DFMSUBTYPE.V2
                else:
                    self.DFMSubType = Enums.DFMSUBTYPE.V1_5
                self.isVersionGetNeeded = False
            

        if(self.isLinkageSetNeeded):                       
            if(self.MP.SendLinkage(self.ID,self.currentLinkage)):                       
                self.isLinkageSetNeeded=False
            else:
                print("Linkage update NACKed")            
                  
        return    

    #endregion     
     

    
#region Module Testing

def ModuleTest():
    Board.BoardSetup()
    #tmp = DFMGroup(COMM.TESTCOMM())
    port = COMM.UARTCOMM()    
    dfm = DFM(8,Enums.DFMTYPE.PLETCHERV3,'hi')
    dfm.ReadValues(False)  
    for sp in dfm.currentStatusPackets:
        print(sp.GetDataBufferPrintPacket())          
       
if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     

#endregion
