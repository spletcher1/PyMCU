import DFM
import COMM
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

class DFMGroup:
    DFMGroup_message = Event.Event()
    DFMGroup_updatecomplete = Event.Event()

    #region Initialization, Messaging, and DFMlist Management
    def __init__(self,commProtocol):
        self.theDFMs = []
        DFM.DFM.DFM_message+=self.NewMessageDirect
        self.stopReadWorkerSignal = False        
        self.stopProgramWorkerSignal = False    
        self.stopRecordingSignal = False
        self.longestQueue = 0
        self.isWriting = False
        self.isReadWorkerRunning = False
        self.isProgramWorkerRunning = False
        self.currentOutputDirectory = "./"
        self.theCOMM = commProtocol
        COMM.UARTCOMM.UART_message+=self.NewMessageDirect
        Program.MCUProgram.Program_message+=self.NewMessageDirect
        self.theMessageList = MessagesList.MessageList()
        self.currentProgram=Program.MCUProgram()       
        self.activeDFM=None 
        ## New members added when the write worker was disbanded
        self.theFiles = []
        self.writeStartTimes=[]
        self.currentDFMIndex=0


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

    def FindDFMs(self,maxNum=16,startReading=True):              
        for i in range(1,maxNum+1):
            if(self.theCOMM.PollSlave(i)):
                self.theDFMs.append(DFM.DFM(i,self.theCOMM))
                s = "DFM "+str(i)+" found"
                self.NewMessage(i, datetime.datetime.today(), 0, s, Enums.MESSAGETYPE.NOTICE)        
            time.sleep(0.100)  
        if(len(self.theDFMs)>0):               
            self.activeDFM = self.theDFMs[0]
        if(startReading):
            time.sleep(0.500) # This is to avoid an empty packet being sent given the buffer reset upon polling.             
            self.StartReadWorker()
    #endregion

    #region Reading and Recording
    def StartRecording(self):
        if len(self.theDFMs)==0:
            return False    
        self.theMessageList.ClearMessages()
        for i in self.theDFMs:            
            i.ResetOutputFileStuff()
            i.SetStatus(Enums.CURRENTSTATUS.RECORDING)            
            i.isBufferResetNeeded=True   
            i.currentLinkage=self.currentProgram.GetLinkage(i.ID)  
            i.isLinkageSetNeeded=True
        time.sleep(1) # To allow everyone to reset
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
        for d in self.theDFMs:
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
        self.theFiles = []
        self.writeStartTimes=[]
        for d in self.theDFMs:
            self.writeStartTimes.append(datetime.datetime.today())
            tmp=self.currentOutputDirectory+"/"+d.outputFile
            tmp2=open(tmp,"w+")            
            tmp2.write(header)
            self.theFiles.append(tmp2)

        self.stopRecordingSignal=False
        self.isWriting=True
        self.currentDFMIndex=0 

    def WriteStep(self):
        currentDFM = self.theDFMs[self.currentDFMIndex]
        currentDuration=datetime.datetime.today()-self.writeStartTimes[self.currentDFMIndex]
        if(currentDuration.total_seconds()>=86400):
            self.theFiles[self.currentDFMIndex].close()   
            currentDFM.IncrementOutputFile()                
            tmp=self.currentOutputDirectory+"/"+currentDFM.outputFile
            tmp2=open(tmp,"w+") 
            header="Date,Time,MSec,Sample,W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,Temp,Humid,LUX,VoltsIn,Dark,OptoFreq,OptoPW,OptoCol1,OptoCol2,Error,Index\n"           
            tmp2.write(header)
            self.theFiles[self.currentDFMIndex]=tmp2
            self.writeStartTimes[self.currentDFMIndex]=datetime.datetime.today()
        elif(currentDFM.theData.ActualSize()>(200 +(self.currentDFMIndex*2))):
            ss=currentDFM.theData.PullAllRecordsAsString()
            if(ss!=""):                    
                self.theFiles[self.currentDFMIndex].write(ss)                   
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
        for i in range(0,len(self.theDFMs)):
            ss=self.theDFMs[i].theData.PullAllRecordsAsString()
            if(ss!=""):               
                self.theFiles[i].write(ss)
                self.theFiles[i].close()                
        self.NewMessage(0, datetime.datetime.today(), 0, "Recording ended", Enums.MESSAGETYPE.NOTICE)        
        self.WriteMessages()
        self.isWriting=False      
        for d in self.theDFMs:
            d.SetStatus(Enums.CURRENTSTATUS.READING)         
    
    #This function is no longer used.
    def WriteWorker(self):        
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
        theFiles = []
        writeStartTimes=[]
        for d in self.theDFMs:
            writeStartTimes.append(datetime.datetime.today())
            tmp=self.currentOutputDirectory+"/"+d.outputFile
            tmp2=open(tmp,"w+")            
            tmp2.write(header)
            theFiles.append(tmp2)

        self.isWriting=True
        currentDFMIndex=0
        while self.stopRecordingSignal==False:
            currentDFM = self.theDFMs[currentDFMIndex]
            currentDuration=datetime.datetime.today()-writeStartTimes[currentDFMIndex]
            if(currentDuration.total_seconds()>=86400):
                theFiles[currentDFMIndex].close()   
                currentDFM.IncrementOutputFile()                
                tmp=self.currentOutputDirectory+"/"+currentDFM.outputFile
                tmp2=open(tmp,"w+")            
                tmp2.write(header)
                theFiles[currentDFMIndex]=tmp2
                writeStartTimes[currentDFMIndex]=datetime.datetime.today()
            elif(currentDFM.theData.ActualSize()>(200 +(currentDFMIndex*2))):
                ss=currentDFM.theData.PullAllRecordsAsString()
                if(ss!=""):                    
                    theFiles[currentDFMIndex].write(ss)                   
                self.WriteMessages()
           
            tmpLQ=0
            for d in self.theDFMs:
                if(d.theData.ActualSize()>tmpLQ):
                    tmpLQ = d.theData.ActualSize()
            self.longestQueue = tmpLQ
           
            currentDFMIndex+=1
            if(currentDFMIndex==len(self.theDFMs)):
                currentDFMIndex=0
            
            time.sleep(0.1) # sleep awhile to let others take over
        
        # Make sure all data are actually written
        for i in range(0,len(self.theDFMs)):
            ss=self.theDFMs[i].theData.PullAllRecordsAsString()
            if(ss!=""):               
                theFiles[i].write(ss)
                theFiles[i].close()                
        self.NewMessage(0, datetime.datetime.today(), 0, "Recording ended", Enums.MESSAGETYPE.NOTICE)        
        self.WriteMessages()
        self.isWriting=False      
        for d in self.theDFMs:
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
        for d in self.theDFMs:
            d.SetStatus(Enums.CURRENTSTATUS.READING)      
        self.stopReadWorkerSignal=False
        readThread = threading.Thread(target=self.ReadWorker)        
        readThread.start()    

    def StartProgramWorker(self):
        if(len(self.theDFMs)==0): 
            return     
        for d in self.theDFMs:
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

    def ProgramWorker(self):
        self.isProgramWorkerRunning=True        
        tt = datetime.datetime.today()        
        lastTime = time.time()    
        lastSecond = tt.second      
        while True:   
            tt = datetime.datetime.today()
            if(tt.microsecond>0 and tt.second != lastSecond):   
                if(time.time()-lastTime)>1:
                    s="Missed one second"                        
                    self.NewMessage(0,tt,0,s,Enums.MESSAGETYPE.ERROR)                       
                for d in self.theDFMs:
                    ## It takes a little over 30ms to call and
                    ## receive the data from one DFM, given a baud
                    ## rate of 115200                     
                    d.ReadValues(self.isWriting)                                                      
                    time.sleep(0.005)      
                if(self.isWriting):
                    if(self.stopRecordingSignal):
                        self.WriteEnder()                            
                    else:
                        self.WriteStep()                                                                           
                DFMGroup.DFMGroup_updatecomplete.notify()                                                                               
                lastSecond=tt.second    
                lastTime=time.time()                                      
            if(self.stopProgramWorkerSignal):
                for d in self.theDFMs:
                    d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
                self.isProgramWorkerRunning = False                
                return                
            time.sleep( 0.020 ) # Yeild to other threads for a bit

    def ReadWorker(self):    
        self.isReadWorkerRunning=True    
        lastTime = time.time()    
        while True:           
            if(time.time()-lastTime>.2):                                   
                if self.activeDFM != None:
                    self.activeDFM.ReadValues(False)                
                lastTime = time.time()                    
                DFMGroup.DFMGroup_updatecomplete.notify()                                                                         
            if(self.stopReadWorkerSignal):
                for d in self.theDFMs:
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
                for d in self.theDFMs:
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
        for d in self.theDFMs:            
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
        self.StopProgramWorker()  
        self.currentProgram.isActive=False
        self.StartReadWorker()
        self.SetDFMIdleStatus()
        print("Done")
    
    def StageCurrentProgram(self):
        if(len(self.theDFMs)==0):
            return
        self.StopReadWorker()
        print("Baselining")
        self.currentProgram.isActive=True
        for d in self.theDFMs:
            if(self.currentProgram.autoBaseline==True):
                d.BaselineDFM()
            else:
                d.ResetBaseline()   
        self.StartProgramWorker()
        print("Staging program.")                           
    #endregion

#region Module Testing    
def ModuleTest():
    Board.BoardSetup()
    #tmp = DFMGroup(COMM.TESTCOMM())
    tmp = DFMGroup(COMM.UARTCOMM())
    tmp.FindDFMs(1,False)
    print("DFMs Found:" + str(len(tmp.theDFMs)))
    tmp.LoadSimpleProgram(datetime.datetime.today(),datetime.timedelta(minutes=3))
    print(tmp.currentProgram)
    #tmp.ActivateCurrentProgram()  
    while(1):
        tt = datetime.datetime.today()
        if(tt.microsecond>0 and tt.second != lastSecond): 
            tmp.theDFMs[0].ReadValues(False)
            lastSecond=tt.second
            for i in range(0,5):
                print(tmp.theDFMs[0].currentStatusPackets[i].GetConsolePrintPacket())         
    #    tmp.UpdateDFMStatus()     
    #    print(tmp.longestQueue)
    #    time.sleep(1)
    

if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     
#endregion
