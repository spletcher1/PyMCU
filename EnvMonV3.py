import StatusPacket
import Enums
import time
import DataBuffer
import DFMErrors
import Message
import Event
import Instruction

class EnvironmentalMonitorV3:
    EM_message = Event.Event()    
    #region Initialization, etc.
    def __init__(self,mp):
        self.MP = mp
        self.ID=99             
        self.DFMType = Enums.DFMTYPE.ENVMONV3   
        self.outputFile = "EnvMon_0.csv"
        self.outputFileIncrementor=0
        self.status = Enums.CURRENTSTATUS.UNDEFINED
        self.pastStatus = Enums.PASTSTATUS.ALLCLEAR        
        self.theData = DataBuffer.DataBuffer()             
        self.sampleIndex=1
        self.currentInstruction = Instruction.DFMInstruction()
        self.isBufferResetNeeded=False
        self.retryTime=0.0
        self.currentDFMErrors = DFMErrors.DFMErrors()
        self.reportedTemperature=1.0
        self.reportedDarkState = Enums.DARKSTATE.OFF
        self.reportedHumidity=1.0
        self.reportedLUX=0

        self.reportedOptoFrequency=0
        self.reportedOptoPulsewidth=0
        self.reportedOptoStateCol1=0
        self.reportedOptoStateCol2=0        
        self.reportedVoltsIn=0.0       
        # Shown on the DFM page; the EnvMon is not asked for its firmware version.
        self.firmwareVersion=""
        self.isCalculatingBaseline=False                     
        
    def __str__(self):
        return "EnvMon"

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)        
        EnvironmentalMonitorV3.EM_message.notify(tmp)        
    #endregion
  
    #region Property-like getters and setters  

    def GetDFMName(self):
        return "EnvMon"
          
    def SetIdleStatus(self):
        ## Idle is opto off, dark running as its has been, and default other parameters.
        self.currentInstruction = Instruction.DFMInstruction()

    def SetOutputsOn(self):
        pass

    def SetOutputsOff(self):       
        pass

    def SetStatus(self, newStatus):
        if(newStatus != self.status):
            if(newStatus == Enums.CURRENTSTATUS.ERROR or newStatus == Enums.CURRENTSTATUS.MISSING):               
                self.pastStatus = Enums.PASTSTATUS.PASTERROR          
            self.status = newStatus
    #endregion
    def GetLastAnalogData(self,adjustForBaseline):
        # Adjust for baseline has no effect for EnvMon
        tmp = self.theData.GetLastDataPoint()
        if(tmp.sample==0):
            return None
        return tmp.analogValues
        
    #region Packet processing, reading, writing, file methods.  
    def UpdateReportedValues(self, currentStatusPackets):
        self.reportedHumidity = currentStatusPackets[-1].humidity
        self.reportedLUX = currentStatusPackets[-1].lux
        self.reportedTemperature = currentStatusPackets[-1].temp
             
        if(currentStatusPackets[-1].darkStatus==0):
            self.reportedDarkState = Enums.DARKSTATE.OFF
        else:
            self.reportedDarkState = Enums.DARKSTATE.ON

        for sp in currentStatusPackets:
            self.currentDFMErrors.UpdateErrors(sp.errorFlags)             
            if(sp.errorFlags!=0):
                s="Environmental Monitor error code: {:02X}".format(sp.errorFlags)                
                self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,s,Enums.MESSAGETYPE.WARNING)     

    def ProcessPackets(self,currentStatusPackets,saveDataToQueue):                                  
        for j in range(0,len(currentStatusPackets)):                  
            isSuccess=False       
            if(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR):            
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="Checksum mismatch"
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.NOTICE)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.NOANSWER):
                self.SetStatus(Enums.CURRENTSTATUS.MISSING)
                s="No answer"
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.NOTICE)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="Packet size mismatch"
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.NOTICE)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.INCOMPLETEPACKET):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="Incomplete packet received"
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.NOTICE)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.OKAY):              
                isSuccess=True
            if isSuccess:                                                                                                                                            
                if (currentStatusPackets[j].recordIndex>0):                                                   
                    currentStatusPackets[j].sample = self.sampleIndex
                    if(self.theData.NewData(currentStatusPackets[j],saveDataToQueue)==False):     
                        s="Data buffer full: record lost"
                        self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.ERROR)
                        self.SetStatus(Enums.CURRENTSTATUS.ERROR)                       
                    else:                                  
                        if(saveDataToQueue): 
                            self.sampleIndex+=1                                                       
                            self.SetStatus(Enums.CURRENTSTATUS.RECORDING)
                        else:
                            self.SetStatus(Enums.CURRENTSTATUS.READING)                                                     
                else :
                    # It's okay now to receive these because of the fast buffer reset and call.
                    s="({:d}) Empty packet received".format(self.ID)
                    #self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].recordIndex,s,Enums.MESSAGETYPE.NOTICE)                                       
                    print(s)
  
        if(isSuccess):
            self.UpdateReportedValues(currentStatusPackets) 

        self.CheckStatus()

    def ResetOutputFileStuff(self):
        self.outputFileIncrementor=0
        self.outputFile="EnvMon_0.csv"       
    
    def IncrementOutputFile(self):
        self.outputFileIncrementor+=1
        self.outputFile="EnvMon_"+str(self.outputFileIncrementor)+".csv"

    #endregion
    #region DFM Compatibility
    def ResetBaseline(self):
        pass
    def UpdateBaseline(self):
        pass
    def BaselineDFM(self):
        pass
    def SetLinkage(self,links):
        pass
    #endregion

    #region Updating                
 
    def UpdateInstruction(self,instruct,useBaseline,index=None,cycle=None):
        # Kept for the program description only: the EnvMon has no instruction command yet.
        if(instruct is not None):
            self.currentInstruction = instruct
    
    def CheckStatus(self):       
        if self.status == Enums.CURRENTSTATUS.MISSING or self.status == Enums.CURRENTSTATUS.ERROR or self.status == Enums.CURRENTSTATUS.UNDEFINED:            
            return      
        if(self.isBufferResetNeeded and time.monotonic() >= self.retryTime):
            if(self.MP.SendBufferReset(self.ID)):
                self.isBufferResetNeeded=False
                self.sampleIndex=1
            else:
                print("Buffer reset NACKed")
                # Retried, but not on every pass.
                self.retryTime = time.monotonic() + 1.0
        ## TODO: activate instructions for outputs. There is no EnvMon instruction command in
        ## the protocol yet, so nothing is sent.

    #endregion     
     

    
#region Module Testing

def ErrorTest():
    dfm = EnvironmentalMonitorV3(3)
    spList=[]
    for i in range(0,10):
        sp = StatusPacket.StatusPacket(i,99,Enums.DFMTYPE.ENVMONV3)
        if(i==9):
            sp.errorFlags=64
        spList.append(sp)
    dfm.UpdateReportedValues(spList)

if __name__=="__main__" :
    ErrorTest()   
    print("Done!!")     

#endregion
