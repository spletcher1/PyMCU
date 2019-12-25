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
    def __init__(self,commProtocol):
        self.theDFMs = []
        DFM.DFM.DFM_message+=self.NewMessageDirect
        self.stopReadingSignal = False
        self.stopRecordingSignal = False
        self.longestQueue = 0
        self.isWriting = False
        self.isReading = False
        self.currentOutputDirectory = ""
        self.theCOMM = commProtocol
        COMM.UARTCOMM.UART_message+=self.NewMessageDirect
        Program.MCUProgram.Program_message+=self.NewMessageDirect
        self.theMessageList = MessagesList.MessageList()
        self.currentProgram=Program.MCUProgram()        

    def NewMessageDirect(self,newMessage):        
        self.theMessageList.AddMessage(newMessage)     
        DFMGroup.DFMGroup_message.notify(newMessage)
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        self.theMessageList.AddMessage(tmp)  
        DFMGroup.DFMGroup_message.notify(tmp)      
    def ClearDFMList(self):
        self.theDFMs.clear()

    def StartRecording(self):
        if len(self.theDFMs)==0:
            return False
        if self.isReading==False:
            self.StartReading()
        for i in self.theDFMs:
            i.sampleIndex=1
            i.ResetOutputFileStuff()
            i.SetStatus(Enums.CURRENTSTATUS.RECORDING)
        self.stopRecordingSignal=False
        self.theMessageList.ClearMessages()
        self.NewMessage(0, datetime.datetime.today(), 0, "Recording started", Enums.MESSAGETYPE.NOTICE)
        writeThread = threading.Thread(target=self.WriteWorker)
        writeThread.start()
        return True

    def StopRecording(self):
        if len(self.theDFMs)==0:
            return
        self.stopRecordingSignal=True
    
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
            d.SetDFMIdleStatus()
    
    def WriteWorker(self):        
        dt=datetime.datetime.today()
        self.currentOutputDirectory=platform.node()+"_"+dt.strftime("%m_%d_%Y_%H_%M")
        try:
            os.mkdir(self.currentOutputDirectory)
        except OSError:
            self.NewMessage(0, datetime.datetime.today(), 0, "Create directory failed", Enums.MESSAGETYPE.ERROR)                    
        self.WriteProgram()

        header="Date,Time,MSec,Sample,W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,Temp,Humid,LUX,VoltsIn,Dark,OptoFreq,OptoPW,OptoCol1,OptoCol2,Error\n"
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

    def StopReading(self):
        if len(self.theDFMs)==0:
            return
        if(self.isWriting):
            self.stopRecordingSignal = True               
            self.isWriting =False
            time.sleep(0.01)
        self.stopReadingSignal = True
        time.sleep(0.01)       
        self.ClearDFMList()     
    def StartReading(self):
        if(len(self.theDFMs)==0): 
            return
        for d in self.theDFMs:
            d.SetStatus(Enums.CURRENTSTATUS.READING)        
        readThread = threading.Thread(target=self.ReadWorker)
        readThread.start()
    def ReadWorker(self):    
        self.isReading=True
        tt = datetime.datetime.today()
        lastSecond=tt.second
        lastTime = time.time()
        while True:   
            tt = datetime.datetime.today()
            if(tt.microsecond>0 and tt.second != lastSecond):   
                    if(time.time()-lastTime)>1:
                        s="Missed one second"
                        print(s)
                        self.NewMessage(0,tt,0,s,Enums.MESSAGETYPE.ERROR)                       
                    for d in self.theDFMs:
                        ## It takes a little over 30ms to call and
                        ## receive the data from one DFM, given a baud
                        ## rate of 115200
                        d.ReadValues(tt,self.isWriting)        
                        lastSecond=tt.second    
                        lastTime=time.time()
                        time.sleep(0.010)                    
            if(self.stopReadingSignal):
                for d in self.theDFMs:
                    d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
                self.isReading = False                
                return                      
            time.sleep( 0.005 ) # Yeild to other threads for a bit
    

    ## Below here are really the only methods that should be called by 
    ## a GUI or ViewModel
    def LoadTextProgram(self,programPath):
        f=open(programPath,encoding="utf-8-sig")
        lines = f.readlines()
        f.close()
        self.currentProgram.LoadProgram(lines)
        for d in self.theDFMs:           
            d.optoLid.lidType = self.currentProgram.GetLidType(d.ID)
       

    def FindDFMs(self,maxNum=16,startReading=True):
        self.StopReading()        
        for i in range(1,maxNum+1):
            if(self.theCOMM.PollSlave(i)):
                self.theDFMs.append(DFM.DFM(i,self.theCOMM))
            time.sleep(0.01)
        if(startReading):
            self.StartReading()

    ## This function is the one that should be called by an external timer
    ## to keep things rolling correctly.
    def UpdateProgramStatus(self):
        if(self.currentProgram.isActive):
            if(len(self.theDFMs)>0 and self.currentProgram.IsDuringExperiment() and (self.isWriting==False)):
                if(self.isReading==False): 
                    self.StartReading()
                self.StartRecording()
            elif(self.currentProgram.IsAfterExperiment() and self.currentProgram.isActive):
                self.StopCurrentProgram()

            if(self.currentProgram.IsDuringExperiment()):
                self.UpdateDFMInstructions()

    def UpdateDFMInstructions(self):
        for d in self.theDFMs:            
            d.UpdateInstruction(self.currentProgram.GetCurrentInstruction(d.ID),self.currentProgram.autoBaseline)    
            
    def LoadSimpleProgram(self,startTime,duration):
        self.currentProgram.CreateSimpleProgram(startTime,duration)
    
    def StopCurrentProgram(self):
        print("Stopping program.")
        self.currentProgram.isActive=False
        self.StopRecording()
        self.SetDFMIdleStatus()
    
    def ActivateCurrentProgram(self):
        print("Baselining")
        for d in self.theDFMs:
            if(self.currentProgram.autoBaseline==True):
                d.BaselineDFM()
            else:
                d.ResetBaseline()
        isStillBaselining=True
        while isStillBaselining:
            isStillBaselining=False
            for d in self.theDFMs:
                if d.isCalculatingBaseline:
                    isStillBaselining=True
            time.sleep(.3)
        print("Starting program.")                   
        self.currentProgram.isActive=True

            




def ModuleTest():
    bs = Board.BoardSetup()
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
            tmp.theDFMs[0].ReadValues(datetime.datetime.today(),False)
            lastSecond=tt.second
            for i in range(0,5):
                print(tmp.theDFMs[0].currentStatusPackets[i].GetConsolePrintPacket())         
    #    tmp.UpdateDFMStatus()     
    #    print(tmp.longestQueue)
    #    time.sleep(1)
    

if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     
