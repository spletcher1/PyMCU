import DFM
import time
import Enums
import datetime
import threading
import MessagesList
import Message
import datetime
import platform
import os
import Program
import Event
import Board
import DataGetter

class DFMGroup:
    DFMGroup_message = Event.Event()
    DFMGroup_updatecomplete = Event.Event()
    DFMGroup_programEnded = Event.Event()

    #region Initialization, Messaging, and DFMlist Management
    def __init__(self):
        self.MP = DataGetter.DataGetter() 
        self.theDFMs = {}
        DFM.DFM.DFM_message+=self.NewMessageDirect
        DFM.DFM.DFM_command+=self.DFMCommandReceive
        self.stopReadWorkerSignal = False        
        self.stopProgramWorkerSignal = False    
        self.stopRecordingSignal = False
        self.longestQueue = 0
        self.isWriting = False
        self.isReadWorkerRunning = False
        self.isProgramWorkerRunning = False
        self.currentOutputDirectory = "./"                
        Program.MCUProgram.Program_message+=self.NewMessageDirect
        self.theMessageList = MessagesList.MessageList()
        self.currentProgram=Program.MCUProgram()       
        self.activeDFM=None 
        ## New members added when the write worker was disbanded
        self.theFiles = {}
        self.writeStartTimes={}
        self.currentDFMIndex=0                
        self.currentDFMKeysList=[]


    def NewMessageDirect(self,newMessage):        
        self.theMessageList.AddMessage(newMessage)     
        DFMGroup.DFMGroup_message.notify(newMessage)
        
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        self.theMessageList.AddMessage(tmp)  
        DFMGroup.DFMGroup_message.notify(tmp)      
    
    def DFMCommandReceive(self,newCommand):            
        self.MP.command_q.put(newCommand)

    def ClearDFMList(self):        
        self.StopRecording()
        self.StopProgramWorker()
        self.StopReadWorker()
        self.theDFMs.clear()
        self.activeDFM=None
        self.MP.StopReading()

    def FindDFMs(self,maxNum=12): 
        self.theDFMs.clear()
        # First search UART for V3 DFMs
        # Set UART and wait for answer
        tmpDMFList = self.MP.FindDFM(Enums.COMMTYPE.UART)          
        if(len(tmpDMFList)>0):           
            for i in tmpDMFList:                
                self.theDFMs[i.ID]=DFM.DFM(i.ID,i.DFMType,self.MP)
                s = "DFM "+str(i.ID)+" found"
                self.NewMessage(i.ID, datetime.datetime.today(), 0, s, Enums.MESSAGETYPE.NOTICE)               
            self.currentDFMKeysList = list(self.theDFMs.keys())
            self.activeDFM = self.theDFMs[self.currentDFMKeysList[0]]
            self.SetFastProgramReadInterval()
            self.StartReadWorker()
            time.sleep(0.010)  
        else:
            # Now search I2C for V2 DFM             
            tmpDMFList = self.MP.FindDFM(Enums.COMMTYPE.I2C)
            if(len(tmpDMFList)>0):
                for i in tmpDMFList:                                   
                    self.theDFMs[i.ID]=DFM.DFM(i.ID,i.DFMType,self.MP)
                    s = "DFM "+str(i.ID)+" found"
                    self.NewMessage(i.ID, datetime.datetime.today(), 0, s, Enums.MESSAGETYPE.NOTICE)               
                self.currentDFMKeysList = list(self.theDFMs.keys())
                self.activeDFM = self.theDFMs[self.currentDFMKeysList[0]]
                self.SetFastProgramReadInterval()
                self.StartReadWorker()
            time.sleep(0.010)  
    #endregion

    #region Reading and Recording
    def StartRecording(self):        
        if len(self.theDFMs)==0:
            return False    
        # THis is here to ensure that the queues are cleared and ready for recording.       
        self.MP.PauseReading()        
        self.theMessageList.ClearMessages()
        for i in self.theDFMs.values():            
            i.ResetOutputFileStuff()
            i.SetStatus(Enums.CURRENTSTATUS.RECORDING)            
            i.isBufferResetNeeded=True   
            i.isSetNormalProgramIntervalNeeded=True
            i.currentLinkage=self.currentProgram.GetLinkage(i.ID)  
            i.isLinkageSetNeeded=True
            i.currentDFMErrors.ClearErrors()
        
        command=DataGetter.MP_Command(Enums.COMMANDTYPE.SET_STARTTIME,[datetime.datetime.today()])
        self.MP.QueueCommand(command)
                  
        # All DFMV3 should be at fast program read interval here.
        ## So wait enough time to allow everyone to reset, say 2 seconds
        # To allow everyone to reset and set slow read interval
        time.sleep(0.5)         
        self.stopRecordingSignal=False        
        self.NewMessage(0, datetime.datetime.today(), 0, "Recording started", Enums.MESSAGETYPE.NOTICE)
        self.WriteStarter()     
        self.SetNormalProgramReadInterval()
        self.MP.StartReading()     
        return True

    def StopRecording(self):
        if len(self.theDFMs)==0:
            return
        self.stopRecordingSignal=True
        while(self.isWriting==True):
            time.sleep(.1)        
    
    def WriteProgram(self):
        path=self.currentOutputDirectory+"/Program.txt"
        f=open(path,"w+")
        f.write(str(self.currentProgram))
        f.close()

    def WriteMessages(self):
        path=self.currentOutputDirectory+"/Messages.csv"
        f=open(path,"w+")
        f.write(self.theMessageList.GetMessageStringForFile())    
        f.close()

    def SetDFMIdleStatus(self):
        for d in self.theDFMs.values():
            d.SetIdleStatus()                        

    def WriteStarter(self):
        dt=datetime.datetime.today()
        self.currentOutputDirectory="./FLICData/"+platform.node()+"_"+dt.strftime("%m_%d_%Y_%H_%M")
        try:
            os.mkdir("./FLICData")
        except FileExistsError:
            pass
        try:
            os.mkdir(self.currentOutputDirectory)
        except OSError:
            self.NewMessage(0, datetime.datetime.today(), 0, "Create directory failed", Enums.MESSAGETYPE.ERROR)                    
        self.WriteProgram()

        header="Date,Time,MSec,Sample,W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,Temp,Humid,LUX,VoltsIn,Dark,OptoFreq,OptoPW,OptoCol1,OptoCol2,Error,Index\n"
        self.theFiles.clear()
        self.writeStartTimes.clear()
        for key, value in self.theDFMs.items():
            self.writeStartTimes[key]= datetime.datetime.today()
            tmp=self.currentOutputDirectory+"/"+value.outputFile
            tmp2=open(tmp,"w+")            
            tmp2.write(header)
            self.theFiles[key]=tmp2

        self.stopRecordingSignal=False       
        self.currentDFMIndex=0
        self.isWriting=True
       
    def WriteStep(self):
        currentDFM = self.theDFMs[self.currentDFMKeysList[self.currentDFMIndex]]
        currentDuration=datetime.datetime.today()-self.writeStartTimes[currentDFM.ID]
        if(currentDuration.total_seconds()>=43200):
            self.theFiles[currentDFM.ID].close()   
            currentDFM.IncrementOutputFile()                
            tmp=self.currentOutputDirectory+"/"+currentDFM.outputFile
            tmp2=open(tmp,"w+") 
            header="Date,Time,MSec,Sample,W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,Temp,Humid,LUX,VoltsIn,Dark,OptoFreq,OptoPW,OptoCol1,OptoCol2,Error,Index\n"           
            tmp2.write(header)
            self.theFiles[currentDFM.ID]=tmp2
            self.writeStartTimes[currentDFM.ID]=datetime.datetime.today()
        elif(currentDFM.theData.ActualSize()>(1000 +(self.currentDFMIndex*10))):
            ss=currentDFM.theData.PullAllRecordsAsString()
            if(ss!=""):                    
                self.theFiles[currentDFM.ID].write(ss)                   
            self.WriteMessages()
        
        tmpLQ=0
        for d in self.theDFMs.values():
            if(d.theData.ActualSize()>tmpLQ):
                tmpLQ = d.theData.ActualSize()
        self.longestQueue = tmpLQ
        
        self.currentDFMIndex+=1
        if(self.currentDFMIndex==len(self.theDFMs)):
            self.currentDFMIndex=0 

    def WriteEnder(self):
        for key, value in self.theDFMs.items():
            ss=value.theData.PullAllRecordsAsString()
            if(ss!=""):               
                self.theFiles[key].write(ss)
                self.theFiles[key].close()                
        self.NewMessage(0, datetime.datetime.today(), 0, "Recording ended", Enums.MESSAGETYPE.NOTICE)        
        self.WriteMessages()
        self.isWriting=False      
        for d in self.theDFMs.values():
            d.SetStatus(Enums.CURRENTSTATUS.READING)         
     

    def StopReadWorker(self):
        if len(self.theDFMs)==0:
            return    
        self.stopReadWorkerSignal = True
        while(self.isReadWorkerRunning):
            time.sleep(0.10)   

    def StartReadWorker(self):
        if(len(self.theDFMs)==0): 
            return
        for d in self.theDFMs.values():
            d.SetStatus(Enums.CURRENTSTATUS.READING)      
        self.stopReadWorkerSignal=False
        readThread = threading.Thread(target=self.ReadWorker)        
        readThread.start()    

    def StartProgramWorker(self):
        if(len(self.theDFMs)==0): 
            return     
        for d in self.theDFMs.values():
            d.SetStatus(Enums.CURRENTSTATUS.READING)              
        self.stopProgramWorkerSignal=False
        readThread = threading.Thread(target=self.ProgramWorker)        
        readThread.start()     

    def StopProgramWorker(self):
        if len(self.theDFMs)==0:
            return    
        self.stopProgramWorkerSignal = True
        while(self.isProgramWorkerRunning):
            time.sleep(0.10)                
    
    def SetNormalProgramReadInterval(self):
        if(self.activeDFM.DFMType==Enums.DFMTYPE.PLETCHERV3):
            self.MP.SetReadInterval(5)
        else:
            self.MP.SetReadInterval(0.2)


    def SetFastProgramReadInterval(self):
        if(self.activeDFM.DFMType==Enums.DFMTYPE.PLETCHERV3):
            self.MP.SetReadInterval(0.25)        
        else:
            self.MP.SetReadInterval(0.2)

    def ProgramWorker(self):
        self.isProgramWorkerRunning=True                  
        while True:   
            try:
                tmp = self.MP.data_q.get(block=False)                    
                self.theDFMs[tmp[0].DFMID].ProcessPackets(tmp,self.isWriting)    
                if(tmp[0].DFMID == self.activeDFM.ID):
                    DFMGroup.DFMGroup_updatecomplete.notify()         
            except:
                # Only do this for V3 because V2 will always be fast enough
                # following status packets alone.
                for value in self.theDFMs.values():
                    if(value.DFMType == Enums.DFMTYPE.PLETCHERV3):               
                        value.CheckStatusV3()
                   
              
            if(self.isWriting):
                if(self.stopRecordingSignal):                                     
                    self.WriteEnder()                            
                else:
                    self.WriteStep()                                                                           
                                                                                                       
            if(self.stopProgramWorkerSignal):
                for d in self.theDFMs.values():
                    d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
                self.isProgramWorkerRunning = False                
                return                

            time.sleep(0.020)
         

    def ReadWorker(self):    
        self.isReadWorkerRunning=True                    
        while True:   
            try:             
                tmp = self.MP.data_q.get(block=True)                                                
                self.theDFMs[tmp[0].DFMID].ProcessPackets(tmp,False)                                              
                if(tmp[0].DFMID == self.activeDFM.ID):                                 
                    DFMGroup.DFMGroup_updatecomplete.notify()         
            except:
                pass         
                                                                                       
            if(self.stopReadWorkerSignal):              
                for d in self.theDFMs.values():
                    d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)                
                self.isReadWorkerRunning = False                
                return 
               
            time.sleep( 0.020 ) # Yeild to other threads for a bit
    #endregion

    #region Updating Functions
    ## This function is the one that should be called by an external timer
    ## to keep things rolling correctly.
    def UpdateProgramStatus(self):
        if(self.currentProgram.isActive):
            if(len(self.theDFMs)>0 and self.currentProgram.IsDuringExperiment() and (self.isWriting==False)):
                isBaselineing=False
                for d in self.theDFMs.values():
                    if d.isCalculatingBaseline:
                        isBaselineing = True
                if(isBaselineing): 
                    return
                else:                   
                    self.StartRecording()                    
            elif(self.currentProgram.IsAfterExperiment() and self.currentProgram.isActive):
                self.StopCurrentProgram()

            if(self.currentProgram.IsDuringExperiment()):
                self.UpdateDFMInstructions()

    def UpdateDFMInstructions(self):
        for d in self.theDFMs.values():            
            d.UpdateInstruction(self.currentProgram.GetCurrentInstruction(d.ID),self.currentProgram.autoBaseline)    
    #endregion
    
    #region Program Methods
    def LoadTextProgram(self,programPath):
        f=open(programPath,encoding="utf-8-sig")
        lines = f.readlines()
        f.close()
        result=self.currentProgram.LoadProgram(lines,self.theDFMs)
        if (result==False):            
            self.LoadSimpleProgram(datetime.datetime.today(),datetime.timedelta(minutes=180))
        return result  
        
    def LoadSimpleProgram(self,startTime,duration):
        self.currentProgram.CreateSimpleProgram(startTime,duration)
    
    def StopCurrentProgram(self):
        if(len(self.theDFMs)==0):
            return
        print("Stopping program.")        
        self.StopRecording()         
        self.SetDFMIdleStatus() 
        time.sleep(2)
        self.StopProgramWorker()  
        self.currentProgram.isActive=False
        self.StartReadWorker()  
        DFMGroup.DFMGroup_programEnded.notify()      
        print("Done")
    
    def StageCurrentProgram(self):
        if(len(self.theDFMs)==0):
            return
        self.StopReadWorker()
        print("Baselining")
        self.currentProgram.isActive=True
        for d in self.theDFMs.values():
            if(self.currentProgram.autoBaseline==True):
                d.BaselineDFM()
            else:
                d.ResetBaseline()   
        self.SetFastProgramReadInterval()
        self.StartProgramWorker()
        print("Staging program.")                           
    #endregion

#region Module Testing    
def ModuleTest():
    Board.BoardSetup()
    tmp = DFMGroup()
    tmp.FindDFMs(maxNum=7)
    time.sleep(10800)
    tmp.StopReadWorker()
    time.sleep(1)
    while tmp.MP.message_q.empty() != True:
        tmp2 = tmp.MP.message_q.get()
        print(tmp2.message)

    #print("DFMs Found:" + str(len(tmp.theDFMs)))
    #tmp.LoadSimpleProgram(datetime.datetime.today(),datetime.timedelta(minutes=3))
    #print(tmp.currentProgram)
    #tmp.ActivateCurrentProgram()      
    #while(1):        
    #    tmp.theDFMs[0].ReadValues(True)
    #    print(tmp.theDFMs[0].theData.GetLastDataPoint().GetConsolePrintPacket())   
    #    time.sleep(1)      
    #    tmp.UpdateDFMStatus()     
    #    print(tmp.longestQueue)
    #    time.sleep(1)
    

if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     
#endregion
