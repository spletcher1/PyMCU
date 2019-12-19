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

class DFMGroup:
    def __init__(self,commProtocol):
        self.theDFMs = []
        self.stopReadingSignal = False
        self.stopRecordingSignal = False
        self.longestQueue = 0
        self.isWriting = False
        self.isReading = False
        self.currentOutputDirectory = ""
        self.theCOMM = commProtocol
        self.theMessageList = MessagesList.MessageList()
        self.currentProgram=Program.MCUProgram()        

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        self.theMessageList.AddMessage(tmp)        
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

    def LoadProgram(self,programPath):
        f=open(programPath,encoding="utf-8-sig")
        lines = f.readlines()
        f.close()
        self.currentProgram.LoadProgram(lines)
        for d in self.theDFMs:           
            d.optoLid.lidType = self.currentProgram.GetLidType(d.ID)
            d.SetTargetOptoFrequency(self.currentProgram.GetOptoFrequency(d.ID))
            d.SetTargetOptoPW(self.currentProgram.GetOptoPulsewidth(d.ID))
            d.optoDecay=self.currentProgram.GetOptoDecay(d.ID)
            d.optoDelay=self.currentProgram.GetOptoDelay(d.ID)
            d.maxTimeOn=self.currentProgram.GetMexTimeOn(d.ID)

    def UpdateDFMPrograms(self):
        for d in self.theDFMs:
            di = self.currentProgram.GetCurrentInstruction(d.ID)
            if(di.theDarkState == Enums.DARKSTATE.OFF):
                d.isInDark=False
            elif(di.theDarkState == Enums.DARKSTATE.ON):
                d.isInDark=True
            d.SetAllSignalThresholds(di.optoValues)

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
            time.sleep(0.01)
        self.stopReadingSignal = True
        time.sleep(0.01)
        self.isReading = False
        self.ClearDFMList()
  
    def FindDFMs(self,maxNum=16):
        self.StopReading()        
        for i in range(1,maxNum+1):
            if(self.theCOMM.PollSlave(i)):
                self.theDFMs.append(DFM.DFM(i,self.theCOMM))
            time.sleep(0.01)
    def StartReading(self):
        if(len(self.theDFMs)==0): 
            return
        for d in self.theDFMs:
            d.SetStatus(Enums.CURRENTSTATUS.READING)        
        readThread = threading.Thread(target=self.ReadWorker)
        readThread.start()

    def ReadWorker(self):
        nextTime=[0,195000,395000,595000,795000]
        #nextTime=[0,500000]     
        indexer=0
        self.isReading=True
        while True:   
            tt = datetime.datetime.today()
            if(indexer==0):
                if(tt.microsecond<nextTime[1]):                    
                    for d in self.theDFMs:
                        d.ReadValues(tt,self.isWriting)            
                    indexer=indexer+1                
            elif(tt.microsecond>nextTime[indexer]):  
                for d in self.theDFMs:
                    d.ReadValues(tt,self.isWriting)                                  
                indexer=indexer+1                
                if indexer==len(nextTime):
                    indexer=0

            if(self.stopReadingSignal):
                for d in self.theDFMs:
                    d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
                self.isReading = False                
                return                      
            time.sleep( 0.0001 ) # Yeild to other threads for a bit




def ModuleTest():
    tmp = DFMGroup(COMM.TESTCOMM())
    tmp.FindDFMs(4)
    tmp.LoadProgram("TestProgram1.txt")    
    tmp.StartReading()
    tmp.StartRecording()    
    endTime=datetime.datetime.today()+datetime.timedelta(seconds=60)
    while(datetime.datetime.today()<endTime):
        #print(tmp.theDFMs[0].theData.GetLastDataPoint().GetConsolePrintPacket())
        print(tmp.longestQueue)
        time.sleep(1)
    tmp.StopRecording()
    time.sleep(1)
    tmp.StopReading()

if __name__=="__main__" :
    ModuleTest()        
