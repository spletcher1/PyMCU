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
import MultiProcessing

class DFMGroup:
    DFMGroup_message = Event.Event()
    DFMGroup_updatecomplete = Event.Event()
    DFMGroup_programEnded = Event.Event()

    #region Initialization, Messaging, and DFMlist Management
    def __init__(self):
        self.theDFMs = {}
        DFM.DFM.DFM_message+=self.NewMessageDirect
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
        self.MP = '' 
        self.currentDFMKeysList=[]


    def NewMessageDirect(self,newMessage):        
        self.theMessageList.AddMessage(newMessage)     
        DFMGroup.DFMGroup_message.notify(newMessage)
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        self.theMessageList.AddMessage(tmp)  
        DFMGroup.DFMGroup_message.notify(tmp)      
    
    def ClearDFMList(self):        
        self.StopRecording()
        self.StopProgramWorker()
        self.StopReadWorker()
        self.theDFMs.clear()
        self.activeDFM=None

    def FindDFMs(self,maxNum=12): 
        self.theDFMs.clear()
        dfmType = Enums.DFMTYPE.PLETCHERV3             
        #for i in range(1,maxNum+1):
            #if(self.theCOMM.PollSlave(i,dfmType)):
            #    self.theDFMs.append(DFM.DFM(i,self.theCOMM,dfmType))
            #    s = "DFM "+str(i)+" found"
            #    self.NewMessage(i, datetime.datetime.today(), 0, s, Enums.MESSAGETYPE.NOTICE)        
        #    time.sleep(0.010)  
        if(len(self.theDFMs)>0):               
            self.activeDFM = self.theDFMs[list(self.theDFMs.keys())[0]]
        else:
            dfmType = Enums.DFMTYPE.PLETCHERV2                     
            self.MP = MultiProcessing.DataGetterI2C()
            tmpDMFList = self.MP.FindDFM(maxNum)
            if(len(tmpDMFList)>0):
                for i in tmpDMFList:                
                    self.theDFMs[i]=DFM.DFM(i,dfmType)
                    s = "DFM "+str(i)+" found"
                    self.NewMessage(i, datetime.datetime.today(), 0, s, Enums.MESSAGETYPE.NOTICE)               
                self.currentDFMKeysList = list(self.theDFMs.keys())
                self.activeDFM = self.theDFMs[self.currentDFMKeysList[0]]
                self.StartReadWorker()
            time.sleep(0.010)  
    #endregion

    #region Reading and Recording
    def StartRecording(self):
        if len(self.theDFMs)==0:
            return False    
        self.theMessageList.ClearMessages()
        for i in self.theDFMs.values():            
            i.ResetOutputFileStuff()
            i.SetStatus(Enums.CURRENTSTATUS.RECORDING)            
            i.isBufferResetNeeded=True   
            i.isSetNormalProgramIntervalNeeded=True
            i.currentLinkage=self.currentProgram.GetLinkage(i.ID)  
            i.isLinkageSetNeeded=True
            i.currentDFMErrors.ClearErrors()
        # All DFM should be at fast program read interval here.
        ## So wait enough time to allow everyone to reset, say 2 seconds
        # To allow everyone to reset and set slow read interval
        time.sleep(0.5)         
        self.stopRecordingSignal=False        
        self.NewMessage(0, datetime.datetime.today(), 0, "Recording started", Enums.MESSAGETYPE.NOTICE)
        self.WriteStarter()
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
        self.isWriting=True
        self.currentDFMIndex=0
       
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
        for d in self.theDFMs:
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
    
    def SetNormalProgramReadInterval(self, ID):
        for d in self.theDFMs.values(): 
            if(ID==255):
                d.isSetNormalProgramIntervalNeeded=True
            elif(d.ID == ID):
                d.isSetNormalProgramIntervalNeeded=True

    def SetFastProgramReadInterval(self, ID):
        for d in self.theDFMs.values(): 
            if(ID==255):
                d.SetFastProgramReadInterval()
            elif(d.ID == ID):
                d.SetFastProgramReadInterval()

    def ProgramWorker(self):
        self.isProgramWorkerRunning=True                        
        for d in self.theDFMs:         
            d.lastReadTime = datetime.datetime.now()
        
        while True:   
            tt = datetime.datetime.now()            
            for d in self.theDFMs:         
                diffTime = tt-d.lastReadTime   
                if(diffTime.total_seconds()>d.programReadInterval):  
                    ##start=time.time()                                               
                    d.ReadValues(self.isWriting)    
                    DFMGroup.DFMGroup_updatecomplete.notify()    
                    ## Tests show that it takes about 250ms to complete a read when
                    ## the read interval is 3 sec. 
                    ## 300ms for 5 sec. 5 seconds seems good assuming max 12 DFM.
                    ##end=time.time()
                    ##print("DFM time: "+str(end-start))     
                    ##print(diffTime.total_seconds())
                    ##print(d.programReadInterval)
                    ##                
                time.sleep(d.programReadInterval/50)  
              
            if(self.isWriting):
                if(self.stopRecordingSignal):                    
                    ## Need to clear out the DFM buffers:
                    for d in self.theDFMs: 
                        d.ReadValues(True)
                        time.sleep(0.010)
                    self.WriteEnder()                            
                else:
                    self.WriteStep()                                                                           
                                                                                                       
            
            if(self.stopProgramWorkerSignal):
                for d in self.theDFMs:
                    d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
                self.isProgramWorkerRunning = False                
                return                

            time.sleep(self.theDFMs[0].programReadInterval/20) # Yeild to other threads for a bit
            #time.sleep(0.200) # Yeild to other threads for a bit

    def ReadWorker(self):    
        self.isReadWorkerRunning=True                    
        while True:   
            try:
                tmp = self.MP.data_q.get(block=True)                                                  
                self.theDFMs[tmp[0].DFMID].ProcessPackets(tmp,False)    
                if(tmp[0].processResult!=Enums.PROCESSEDPACKETRESULT.OKAY):
                    print(tmp[0].GetConsolePrintPacket())

                if(tmp[0].DFMID == self.activeDFM.ID):
                    DFMGroup.DFMGroup_updatecomplete.notify()         
            except:
                pass         
                                                                                       
            if(self.stopReadWorkerSignal):
                self.MP.StopReading(True)
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
        self.SetFastProgramReadInterval(255)
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
