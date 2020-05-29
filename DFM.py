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
    DFM_command = Event.Event()
    #region Initialization, etc.
    def __init__(self,id,dfmType):
        self.ID=id             
        self.DFMType = dfmType   
        self.outputFile = "DFM" + str(self.ID) + "_0.csv"
        self.outputFileIncrementor=0
        self.status = Enums.CURRENTSTATUS.UNDEFINED
        self.pastStatus = Enums.PASTSTATUS.ALLCLEAR
        self.beforeErrorStatus = Enums.CURRENTSTATUS.UNDEFINED
        self.theData = DataBuffer.DataBuffer()             
        self.sampleIndex=1
        self.signalBaselines=array.array("i",(0 for i in range(0,12)))      
        self.currentLinkage = array.array("i",[1,2,3,4,5,6,7,8,9,10,11,12])    
        self.baselineSamples=0
        self.isCalculatingBaseline=False                   
        self.currentInstruction = Instruction.DFMInstruction()
        self.isInstructionUpdateNeeded=False
        self.isBufferResetNeeded=False
        self.isSetNormalProgramIntervalNeeded=False
        self.isLinkageSetNeeded=False
        self.currentDFMErrors = DFMErrors.DFMErrors()
        self.reportedOptoFrequency=0
        self.reportedOptoPulsewidth=0
        self.reportedOptoStateCol1=0
        self.reportedOptoStateCol2=0
        self.reportedTemperature=1.0
        self.reportedDarkState = Enums.DARKSTATE.UNCONTROLLED
        self.reportedHumidity=1.0
        self.reportedLUX=0
        self.reportedVoltsIn=1.0      
        self.bufferResetTime = datetime.datetime.today()
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV3):
            self.programReadInterval=5   
        else:
            self.programReadInterval=0.2
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV2):
            self.theOptoLid = OptoLid.OptoLid()       

    def __str__(self):
        return "DFM " + str(self.ID)

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)        
        DFM.DFM_message.notify(tmp)        
    #endregion
  
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

    def SetIdleStatus(self):
        ## Idle is opto off, dark running as its has been, and default other parameters.
        self.currentInstruction = Instruction.DFMInstruction()
        self.isInstructionUpdateNeeded=True
        ## Do not write to the serial device here because it will collide with its use in the ReadWorker
        ## Thread.  Checkstatus, which should send the default instruction, is handled by that thread.

    def SetOutputsOn(self):
        self.currentInstruction = Instruction.DFMInstruction()
        self.currentInstruction.SetOptoValues([0]*12)
        self.isInstructionUpdateNeeded=True        

    def SetOutputsOff(self):       
        self.currentInstruction = Instruction.DFMInstruction()        
        self.isInstructionUpdateNeeded=True
        
    def SetStatus(self, newStatus):
        if(newStatus != self.status):
            if(newStatus == Enums.CURRENTSTATUS.ERROR):
                self.beforeErrorStatus = self.status
                self.pastStatus = Enums.PASTSTATUS.PASTERROR
            elif(newStatus == Enums.CURRENTSTATUS.RECORDING):
                self.beforeErrorStatus = newStatus
                self.pastStatus = Enums.PASTSTATUS.ALLCLEAR
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
        self.currentDFMErrors.UpdateErrors(currentStatusPackets[-1].errorFlags)
        
        if(currentStatusPackets[-1].darkStatus==0):
            self.reportedDarkState = Enums.DARKSTATE.OFF
        else:
            self.reportedDarkState = Enums.DARKSTATE.ON

        for sp in currentStatusPackets:
            if(sp.errorFlags!=0):
                s="({:d}) Non-zero DFM error code: {:02X}".format(self.ID,sp.errorFlags)
                self.NewMessage(self.ID,sp.packetTime,sp.sample,s,Enums.MESSAGETYPE.WARNING)

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
            if(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR):            
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Checksum error".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.NOANSWER):
                self.SetStatus(Enums.CURRENTSTATUS.MISSING)
                s="({:d}) No answer".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Wrong number of bytes".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.OKAY):
                isSuccess=True
            if isSuccess:                                        
                if (currentStatusPackets[j].recordIndex>0):                                                                       
                    if(self.theData.NewData(currentStatusPackets[j],saveDataToQueue)==False):     
                        s="({:d}) Data queue error".format(self.ID)
                        self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.ERROR)
                        self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                        isSuccess = False
                    else:                        
                        if(self.status == Enums.CURRENTSTATUS.ERROR):
                            self.SetStatus(self.beforeErrorStatus)                                     
                    if(self.isCalculatingBaseline):                        
                        self.UpdateBaseline()
                else :
                    s="({:d}) Empty packet received".format(self.ID)
                    self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.NOTICE)    
  
        self.UpdateReportedValues(currentStatusPackets) 

        if(self.DFMType == Enums.DFMTYPE.PLETCHERV3):               
            self.CheckStatusV3()
        elif(self.DFMType == Enums.DFMTYPE.PLETCHERV2):
            self.CheckStatusV2()
        else:
            pass #Sable V2 doesn't need anything here.

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
            self.SetFastProgramReadInterval()
            self.isSetNormalProgramIntervalNeeded=True
    
    def CheckStatusV2(self):        
        lsp = self.theData.GetLastDataPoint()   
        
        if(lsp.optoFrequency!=self.currentInstruction.frequency):            
            tmpcommand1=MP_Command(Enums.COMMANDTYPE.SEND_FREQ,[self.ID,self.currentInstruction.frequency])
            DFM.DFM_command.notify(tmpcommand1)
        
        if(lsp.optoPulseWidth!=self.currentInstruction.pulseWidth):               
            tmpcommand2=MP_Command(Enums.COMMANDTYPE.SEND_PW,[self.ID,self.currentInstruction.pulseWidth])
            DFM.DFM_command.notify(tmpcommand2)
                
        if(self.currentInstruction.theDarkState!=Enums.DARKSTATE.UNCONTROLLED):                 
            if(lsp.darkStatus!=self.currentInstruction.theDarkState.value[0]):           
                tmpcommand3=MP_Command(Enums.COMMANDTYPE.SEND_DARK,[self.ID,self.currentInstruction.theDarkState.value[0]])
                DFM.DFM_command.notify(tmpcommand3) 


        if(self.isInstructionUpdateNeeded):                
            self.theOptoLid.UpdateWithInstruction(self.currentInstruction)                   
            self.isInstructionUpdateNeeded=False

        self.theOptoLid.SetOptoState(lsp.analogValues)              
        if(lsp.optoState1!=self.theOptoLid.optoStateCol1 or lsp.optoState2!=self.theOptoLid.optoStateCol2):            
            tmpcommand4 = MP_Command(Enums.COMMANDTYPE.SEND_OPTOSTATE,[self.ID,self.theOptoLid.optoStateCol1,self.theOptoLid.optoStateCol2])
            DFM.DFM_command.notify(tmpcommand4)   
        

    # This needs major update
    def CheckStatusV3(self):                
        ## These are else if groups so that both are not executed on the same pass.
        ## Take care to note potential problems with long read intervals.
        if(self.isBufferResetNeeded):
            if self.theCOMM.RequestBufferReset(self):
                #print("Buffer reset success!")
                self.isBufferResetNeeded=False
                self.bufferResetTime = datetime.datetime.today()
                self.sampleIndex=1       
                return                          
            else:
                print("Buffer reset failure")
        elif(self.isInstructionUpdateNeeded):
            if self.theCOMM.SendInstruction(self.ID,self.currentInstruction):
                #print("Instruction success: " + str(self.currentInstruction))                
                self.isInstructionUpdateNeeded=False
                return 
            else:
                print("Instruction failure")
        elif(self.isLinkageSetNeeded):
            if self.theCOMM.SendLinkage(self):                          
                self.isLinkageSetNeeded=False
                return 
                #print("Linkage success: " + str(self.currentLinkage))  
            else:
                print("Linkage failure")
        elif(self.isSetNormalProgramIntervalNeeded):
            self.programReadInterval=5
            self.isSetNormalProgramIntervalNeeded=False   
            return 
        return 

    def SetFastProgramReadInterval(self):
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV3):
            self.programReadInterval=0.5
        else:
            self.programReadInterval=0.2
    
    def GetProgramReadInterval(self):
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV3):
            if self.programReadInterval==5:
                return "normal"
            elif self.programReadInterval==0.5:
                return "fast"
            else:
                return "none"
        else:
            return "normal"


    #endregion     
     

    
#region Module Testing

def ModuleTest():
    Board.BoardSetup()
    #tmp = DFMGroup(COMM.TESTCOMM())
    #port = COMM.UARTCOMM()
    port=COMM.COMM()
    dfm = DFM(6,port,Enums.DFMTYPE.PLETCHERV2)
    dfm.ReadValues(False)  
    for sp in dfm.currentStatusPackets:
        print(sp.GetDataBufferPrintPacket())          
       
if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     

#endregion
