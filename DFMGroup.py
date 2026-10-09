import datetime
import os
import platform
import queue
import threading
import time

import DataGetter
import DFM
import Enums
import EnvMonV3
import Event
import Message
import MessagesList
import Program

DATA_FILE_HEADER = "Date,Time,MSec,Sample,W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,Temp,Humid,LUX,VoltsIn,Dark,OptoFreq,OptoPW,OptoCol1,OptoCol2,Error,Index\n"
# A new data file is started every 12 hours.
DATA_FILE_SECONDS = 43200

class DFMGroup:
    DFMGroup_message = Event.Event()
    DFMGroup_updatecomplete = Event.Event()
    DFMGroup_programEnded = Event.Event()

    #region Initialization, Messaging, and DFMlist Management
    def __init__(self,pcb):
        self.theBoard=pcb
        self.MP = DataGetter.DataGetter()
        self.theDFMs = {}
        DFM.DFM.DFM_message+=self.NewMessageDirect
        EnvMonV3.EnvironmentalMonitorV3.EM_message+=self.NewMessageDirect
        self.stopReadWorkerSignal = False
        self.stopProgramWorkerSignal = False
        self.stopRecordingSignal = False
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
        self.programReadInterval=""

    def NewMessageDirect(self,newMessage):
        if(self.theMessageList.AddMessage(newMessage)):
            DFMGroup.DFMGroup_message.notify(newMessage)

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        self.NewMessageDirect(Message.Message(ID,errorTime,sample,message,mt,-99))

    def ClearDFMList(self):
        self.StopRecording()
        self.StopProgramWorker()
        self.StopReadWorker()
        self.theDFMs.clear()
        self.activeDFM=None
        self.MP.StopReading()
        self.currentProgram.ClearProgram()

    def FindDFMs(self):
        self.theDFMs.clear()
        if(self.theBoard.IsDFMV3Board()):
            commType = Enums.COMMTYPE.UART
        else:
            # Now search I2C for V2 DFM
            commType = Enums.COMMTYPE.I2C
        for i in self.MP.FindDFM(commType):
            if(i.DFMType==Enums.DFMTYPE.ENVMONV3):
                self.theDFMs[i.ID]=EnvMonV3.EnvironmentalMonitorV3(self.MP)
                s = "Environmental monitor found"
            else:
                self.theDFMs[i.ID]=DFM.DFM(i.ID,i.DFMType,self.MP)
                s = "DFM "+str(i.ID)+" found"
            self.NewMessage(i.ID, datetime.datetime.today(), 0, s, Enums.MESSAGETYPE.ANNOTATION)
        if(len(self.theDFMs)==0):
            return
        # Learn each DFM's firmware version now so program compatibility checks and the
        # first instructions use the right packet format. Retried later if this fails.
        for d in self.theDFMs.values():
            if(d.DFMType==Enums.DFMTYPE.PLETCHERV3):
                d.ReadFirmwareVersion()
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
        # This is here to ensure that the queues are cleared and ready for recording.
        self.MP.PauseReading()
        self.MP.ClearQueues()
        self.theMessageList.ClearMessages()
        for i in self.theDFMs.values():
            i.ResetOutputFileStuff()
            i.pastStatus = Enums.PASTSTATUS.ALLCLEAR
            i.status=Enums.CURRENTSTATUS.RECORDING
            i.isBufferResetNeeded=True
            i.SetLinkage(self.currentProgram.GetLinkage(i.ID))
            i.currentDFMErrors.ClearErrors()

        self.MP.SetStartTime()

        # All DFMV3 should be at fast program read interval here.
        ## So wait enough time to allow everyone to reset, say 2 seconds
        # To allow everyone to reset and set slow read interval
        time.sleep(0.5)
        self.stopRecordingSignal=False
        self.NewMessage(0, datetime.datetime.today(), 0, "Recording started", Enums.MESSAGETYPE.ANNOTATION)
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
        with open(self.currentOutputDirectory+"/Program.txt","w+") as f:
            f.write(str(self.currentProgram))

    def WriteMessages(self):
        with open(self.currentOutputDirectory+"/Messages.csv","w+") as f:
            f.write(self.theMessageList.GetMessageStringForFile())

    def SetDFMIdleStatus(self):
        for d in self.theDFMs.values():
            d.SetIdleStatus()

    def _OpenDataFile(self,theDFM):
        f=open(self.currentOutputDirectory+"/"+theDFM.outputFile,"w+")
        f.write(DATA_FILE_HEADER)
        self.theFiles[theDFM.ID]=f
        self.writeStartTimes[theDFM.ID]=datetime.datetime.today()

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
            print("Except: Could not create data directory")
            self.NewMessage(0, datetime.datetime.today(), 0, "Create directory failed", Enums.MESSAGETYPE.ERROR)
        self.WriteProgram()

        self.theFiles.clear()
        self.writeStartTimes.clear()
        for value in self.theDFMs.values():
            self._OpenDataFile(value)

        self.stopRecordingSignal=False
        self.currentDFMIndex=0
        self.isWriting=True

    def WriteStep(self):
        currentDFM = self.theDFMs[self.currentDFMKeysList[self.currentDFMIndex]]
        currentDuration=datetime.datetime.today()-self.writeStartTimes[currentDFM.ID]
        if(currentDuration.total_seconds()>=DATA_FILE_SECONDS):
            self.theFiles[currentDFM.ID].close()
            currentDFM.IncrementOutputFile()
            self._OpenDataFile(currentDFM)
        elif(currentDFM.theData.ActualSize()>(1000 +(self.currentDFMIndex*10))):
            ss=currentDFM.theData.PullAllRecordsAsString()
            if(ss!=""):
                self.theFiles[currentDFM.ID].write(ss)
            self.WriteMessages()

        self.currentDFMIndex+=1
        if(self.currentDFMIndex==len(self.theDFMs)):
            self.currentDFMIndex=0

    def WriteEnder(self):
        try:
            for key, value in self.theDFMs.items():
                # Every file is closed here, including ones with nothing left to write, so
                # their buffered data is on disk before anyone copies it.
                with self.theFiles[key] as f:
                    f.write(value.theData.PullAllRecordsAsString())
            self.NewMessage(0, datetime.datetime.today(), 0, "Recording ended", Enums.MESSAGETYPE.ANNOTATION)
            self.WriteMessages()
        finally:
            self.isWriting=False
            for d in self.theDFMs.values():
                d.SetStatus(Enums.CURRENTSTATUS.READING)

    def SetActiveDFM(self,dfmNum):
        self.activeDFM = self.theDFMs[dfmNum]
        # Only focus DFM is readworker is running (not programworker)
        if self.isReadWorkerRunning:
            self.MP.SetFocusDFM(self.activeDFM.ID)

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
        threading.Thread(target=self.ReadWorker).start()

    def StartProgramWorker(self):
        if(len(self.theDFMs)==0):
            return
        for d in self.theDFMs.values():
            d.SetStatus(Enums.CURRENTSTATUS.READING)
        # Cancel any focus
        self.MP.SetFocusDFM(0)
        self.stopProgramWorkerSignal=False
        threading.Thread(target=self.ProgramWorker).start()

    def StopProgramWorker(self):
        if len(self.theDFMs)==0:
            return
        self.stopProgramWorkerSignal = True
        while(self.isProgramWorkerRunning):
            time.sleep(0.10)

    def _IsV3(self):
        return self.activeDFM.DFMType==Enums.DFMTYPE.PLETCHERV3 or self.activeDFM.DFMType==Enums.DFMTYPE.ENVMONV3

    def SetNormalProgramReadInterval(self):
        self.programReadInterval = "normal"
        self.MP.SetReadInterval(4 if self._IsV3() else 0.2)

    def SetFastProgramReadInterval(self):
        if(self._IsV3()):
            self.programReadInterval = "fast"
            self.MP.SetReadInterval(0.3)
        else:
            self.programReadInterval = "normal"
            self.MP.SetReadInterval(0.2)

    def GetProgramReadInterval(self):
        return self.programReadInterval

    def ProgramWorker(self):
        self.isProgramWorkerRunning=True
        self.MP.SetStatusRequestType(Enums.STATUSREQUESTTYPE.NORMAL)
        # Now clear out the buffers so that you can view the data before recording starts
        # which itself will clear out the buffer.
        for i in self.theDFMs.values():
            i.isBufferResetNeeded=True
        while not self.stopProgramWorkerSignal:
            try:
                tmp = self.MP.data_q.get(block=False)
            except queue.Empty:
                tmp = None
            # Errors are reported, not raised: if this thread died, recording would stop.
            try:
                if tmp is not None:
                    self.theDFMs[tmp[0].DFMID].ProcessPackets(tmp,self.isWriting)
                    if(tmp[0].DFMID == self.activeDFM.ID):
                        DFMGroup.DFMGroup_updatecomplete.notify()
                elif(self._IsV3()):
                    # For V3 only, check status as needed.  Can't do this for V2
                    # because LED updates rely on last data point, which needs to
                    # be updated before another call to CheckStatus.
                    # Leave it up to the PacketProcess function to do this.
                    # But that's okay because those come every 0.2 sec
                    # V3 calls come only every 5 sec so need to update BufferReset
                    # Linkage and Instuction as often as possible.
                    for value in self.theDFMs.values():
                        value.CheckStatus()

                if(self.isWriting):
                    if(self.stopRecordingSignal):
                        self.WriteEnder()
                    else:
                        self.WriteStep()
            except Exception as e:
                print(f"Program worker exception: {e!r}")
            time.sleep(0.001)
        for d in self.theDFMs.values():
            d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
        self.isProgramWorkerRunning = False

    def ReadWorker(self):
        self.isReadWorkerRunning=True
        self.MP.StartReading()
        self.MP.SetStatusRequestType(Enums.STATUSREQUESTTYPE.LATESTONLY)
        while not self.stopReadWorkerSignal:
            # The timeout lets the stop signal be seen even when no data is arriving.
            try:
                tmp = self.MP.data_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if(tmp[-1].DFMID == self.activeDFM.ID):
                    self.theDFMs[tmp[-1].DFMID].ProcessPackets(tmp,False)
                    DFMGroup.DFMGroup_updatecomplete.notify()
            except Exception as e:
                print(f"Read worker exception: {e!r}")
            time.sleep( 0.001 ) # Yeild to other threads for a bit
        for d in self.theDFMs.values():
            d.SetStatus(Enums.CURRENTSTATUS.UNDEFINED)
        self.isReadWorkerRunning = False
    #endregion

    #region Updating Functions
    ## This function is the one that should be called by an external timer
    ## to keep things rolling correctly.
    def UpdateProgramStatus(self):
        if(self.currentProgram.isActive):
            if(len(self.theDFMs)>0 and self.currentProgram.IsDuringExperiment() and (self.isWriting==False)):
                # Wait for baselines to finish before recording.
                if not any(d.isCalculatingBaseline for d in self.theDFMs.values()):
                    self.StartRecording()
            elif(self.currentProgram.IsAfterExperiment()):
                self.StopCurrentProgram()

            if(self.currentProgram.IsDuringExperiment()):
                self.UpdateDFMInstructions()

    def UpdateDFMInstructions(self):
        for d in self.theDFMs.values():
            d.UpdateInstruction(self.currentProgram.GetCurrentInstruction(d.ID),self.currentProgram.autoBaseline)
    #endregion

    #region Program Methods
    def LoadTextProgram(self,programPath):
        with open(programPath,encoding="utf-8-sig") as f:
            lines = f.readlines()
        result=self.currentProgram.LoadProgram(lines,self.theDFMs)
        if (result==False):
            self.LoadSimpleProgram(datetime.datetime.today() + datetime.timedelta(minutes=1),datetime.timedelta(minutes=180))
        return result

    def LoadSimpleProgram(self,startTime,duration):
        self.currentProgram.CreateSimpleProgram(startTime,duration)

    def CheckProgramCompatibility(self):
        # V1.5 firmware takes only 2-byte decay, delay and max time on.
        for d in self.theDFMs.values():
            if(d.DFMType==Enums.DFMTYPE.PLETCHERV3 and d.DFMSubType == Enums.DFMSUBTYPE.V1_5):
                tmp = self.currentProgram.theInstructionSets.get(d.ID)
                if(tmp is not None and tmp.IsVersion1_5Compatible()==False):
                    return False
        return True

    def StopCurrentProgram(self):
        if(len(self.theDFMs)==0):
            return
        # This is here for V3 to make sure all have nearly the
        # same number of observations (not off by 5sec)
        self.SetFastProgramReadInterval()
        time.sleep(1)
        self.MP.PauseReading()
        self.StopRecording()
        self.SetDFMIdleStatus()
        self.StopProgramWorker()
        self.currentProgram.isActive=False
        self.StartReadWorker()
        self.MP.SetFocusDFM(self.activeDFM.ID)
        DFMGroup.DFMGroup_programEnded.notify()

    def StageCurrentProgram(self):
        if(len(self.theDFMs)==0):
            return
        self.StopReadWorker()
        self.currentProgram.isActive=True
        for d in self.theDFMs.values():
            if(self.currentProgram.autoBaseline==True):
                d.BaselineDFM()
            else:
                d.ResetBaseline()
        self.SetFastProgramReadInterval()
        self.StartProgramWorker()
    #endregion
