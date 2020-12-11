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
        self.isInstructionUpdateNeeded=False
        self.isBufferResetNeeded=False
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
        self.isInstructionUpdateNeeded=True

    def SetOutputsOn(self):
        pass

    def SetOutputsOff(self):       
        pass

    def SetStatus(self, newStatus):
        if(newStatus != self.status):
            if(newStatus == Enums.CURRENTSTATUS.ERROR or newStatus == Enums.CURRENTSTATUS.MISSING):               
                self.pastStatus = Enums.PASTSTATUS.PASTERROR
            elif(newStatus == Enums.CURRENTSTATUS.RECORDING):                
                self.pastStatus = Enums.PASTSTATUS.ALLCLEAR
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
                s="({:d}) Non-zero EnvMon error code: {:02X}".format(self.ID,sp.errorFlags)
                self.NewMessage(self.ID,sp.packetTime,sp.sample,s,Enums.MESSAGETYPE.WARNING)     

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
                s="({:d}) Wrong number of bytes:".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.INCOMPLETEPACKET):
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                s="({:d}) Incomplete packet received:".format(self.ID)
                self.NewMessage(self.ID,currentStatusPackets[j].packetTime,self.sampleIndex,s,Enums.MESSAGETYPE.ERROR)                       
            elif(currentStatusPackets[j].processResult == Enums.PROCESSEDPACKETRESULT.OKAY):              
                isSuccess=True
            if isSuccess:                                                                                                                                            
                if (currentStatusPackets[j].recordIndex>0):                                                   
                    currentStatusPackets[j].sample = self.sampleIndex
                    if(self.theData.NewData(currentStatusPackets[j],saveDataToQueue)==False):     
                        s="({:d}) Data queue error".format(self.ID)
                        self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.ERROR)
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
                    self.NewMessage(self.ID,currentStatusPackets[j].packetTime,currentStatusPackets[j].sample,s,Enums.MESSAGETYPE.NOTICE)   
                    self.SetStatus(Enums.CURRENTSTATUS.ERROR)                        
  
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
 
    def UpdateInstruction(self,instruct,useBaseline):                      
        if(instruct is self.currentInstruction):            
            return 
        else:                                  
            self.currentInstruction = instruct                                         
            self.isInstructionUpdateNeeded=True                     
    
    def CheckStatus(self):             
        if(self.isBufferResetNeeded):                  
            if(self.MP.SendBufferReset(self.ID)):                    
                self.isBufferResetNeeded=False
                self.sampleIndex=1      
            else:
                print("Buffer reset NACKed")                 
        
        ## TODO: activate instructions for outputs.
        if(self.isInstructionUpdateNeeded):            
            if(self.MP.SendInstruction(self.ID, self.currentInstruction)):                       
                self.isInstructionUpdateNeeded=False                 
            else:
                print("Instruction update NACKed")                           
                  
        return    

    #endregion     
     

    
#region Module Testing

def ModuleTest():
    Board.BoardSetup()
    #tmp = DFMGroup(COMM.TESTCOMM())
    #port = COMM.UARTCOMM()
    port=COMM.COMM()
    dfm = EnvironmentalMonitorV3(3)
    dfm.ReadValues(False)  
    for sp in dfm.currentStatusPackets:
        print(sp.GetDataBufferPrintPacket())          
       
if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     

#endregion
