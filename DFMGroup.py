import datetime
import os
import platform
import queue
import threading
import time

import COMM
import DataGetter
import DFM
import Enums
import EnvMonV3
import Event
import Message
import MessagesList
import Program
import StatusPacket

# DFM data files add the Paradigm columns; the Environmental Monitor's keep the old ones.
DATA_FILE_HEADER = StatusPacket.DATA_COLUMNS + "," + StatusPacket.PARADIGM_COLUMNS + "\n"
ENVMON_FILE_HEADER = StatusPacket.DATA_COLUMNS + "\n"
# A new data file is started every 12 hours.
DATA_FILE_SECONDS = 43200
# Each DFM's records are written this often. The DFM drops records once they are acknowledged,
# so a crash or power cut loses at most about this much.
WRITE_SECONDS = 10
# How long the end of a Program waits for every DFM to acknowledge its all-off instruction.
PROGRAM_END_SECONDS = 3

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
        # When each DFM's buffered records are next written (time.monotonic()).
        self.nextWriteTimes={}
        # The message list's change count when Messages.csv was last written.
        self.messagesWrittenAt=None
        # DFMs whose last data file write failed, so the failure is reported only once.
        self.writeFailedIDs=set()
        self.currentDFMIndex=0
        self.currentDFMKeysList=[]
        self.programReadInterval=""
        # True while a staged program waits for its start time, reading only the DFM on screen.
        self.isStagedFocused=False

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
        # Every DFM is recorded, so every DFM is read again.
        self.isStagedFocused=False
        self.MP.SetFocusDFM(0)
        self.theMessageList.ClearMessages()
        for i in self.theDFMs.values():
            i.ResetOutputFileStuff()
            i.pastStatus = Enums.PASTSTATUS.ALLCLEAR
            i.status=Enums.CURRENTSTATUS.RECORDING
            i.isBufferResetNeeded=True
            i.SetLinkage(self.currentProgram.GetLinkage(i.ID))
            i.currentDFMErrors.ClearErrors()
            # Baselines come from the first readings of the recording, taken after the buffer
            # reset, never from before the start time.
            if(self.currentProgram.autoBaseline):
                i.BaselineDFM()
            else:
                i.ResetBaseline()

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

    def WriteMessages(self, force=False):
        """Writes Messages.csv, unless no message has been added since the last time."""
        changeCount = self.theMessageList.changeCount
        if(not force and changeCount == self.messagesWrittenAt):
            return
        with open(self.currentOutputDirectory+"/Messages.csv","w+") as f:
            f.write(self.theMessageList.GetMessageStringForFile())
        self.messagesWrittenAt = changeCount

    def SetDFMIdleStatus(self):
        for d in self.theDFMs.values():
            d.SetIdleStatus()

    def _OpenDataFile(self,theDFM):
        f=open(self.currentOutputDirectory+"/"+theDFM.outputFile,"w+")
        f.write(ENVMON_FILE_HEADER if theDFM.DFMType==Enums.DFMTYPE.ENVMONV3 else DATA_FILE_HEADER)
        self.theFiles[theDFM.ID]=f
        self.writeStartTimes[theDFM.ID]=datetime.datetime.today()
        self.nextWriteTimes[theDFM.ID]=time.monotonic()+WRITE_SECONDS

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
        self.writeFailedIDs.clear()
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
        elif(time.monotonic() >= self.nextWriteTimes[currentDFM.ID]):
            # A failed write is also tried again only then, not on every pass.
            self.nextWriteTimes[currentDFM.ID] = time.monotonic()+WRITE_SECONDS
            if(self._WriteBufferedData(currentDFM)):
                self.WriteMessages()

        self.currentDFMIndex+=1
        if(self.currentDFMIndex==len(self.theDFMs)):
            self.currentDFMIndex=0

    def _WriteBufferedData(self,theDFM):
        """Writes the DFM's buffered records to its data file. Returns False if that failed; the
        records are then kept for the next try. A try after a partial write can repeat some
        rows, which the Index column shows."""
        lines, count = theDFM.theData.PeekRecordsAsString()
        if(count==0):
            return True
        try:
            f = self.theFiles[theDFM.ID]
            f.write(lines)
            # Flushed so that a failure shows up now, while the records can still be kept.
            f.flush()
        except (OSError, ValueError) as e:
            print(f"Data file write failed ({theDFM.ID}): {e!r}")
            # Writes are retried on every pass, so this is reported once until one succeeds.
            if(theDFM.ID not in self.writeFailedIDs):
                self.writeFailedIDs.add(theDFM.ID)
                self.NewMessage(theDFM.ID, datetime.datetime.today(), 0, "({:d}) Data file write failed: {}".format(theDFM.ID, e), Enums.MESSAGETYPE.ERROR)
            return False
        theDFM.theData.RemoveRecords(count)
        self.writeFailedIDs.discard(theDFM.ID)
        return True

    def WriteEnder(self):
        try:
            for key, value in self.theDFMs.items():
                # Records held after a DFM restarted go in before the file is closed.
                if hasattr(value, "FlushPendingRecords"):
                    value.FlushPendingRecords()
                # Each file is written and closed on its own, so one that fails doesn't keep the
                # others' data off the disk. Every file is closed, including ones with nothing left
                # to write, so their buffered data is on disk before anyone copies it.
                if not self._WriteBufferedData(value):
                    # The recording is over, so these would otherwise end up in the next one's file.
                    count = value.theData.ActualSize()
                    self.NewMessage(key, datetime.datetime.today(), 0, "({:d}) {:d} records could not be written".format(key, count), Enums.MESSAGETYPE.ERROR)
                    value.theData.RemoveRecords(count)
                try:
                    self.theFiles[key].close()
                except OSError as e:
                    self.NewMessage(key, datetime.datetime.today(), 0, "({:d}) Data file close failed: {}".format(key, e), Enums.MESSAGETYPE.ERROR)
            self.NewMessage(0, datetime.datetime.today(), 0, "Recording ended", Enums.MESSAGETYPE.ANNOTATION)
            self.WriteMessages(force=True)
        finally:
            self.isWriting=False
            for d in self.theDFMs.values():
                d.SetStatus(Enums.CURRENTSTATUS.READING)

    def SetActiveDFM(self,dfmNum):
        self.activeDFM = self.theDFMs[dfmNum]
        # Only one DFM is read when no program is running and while a staged program waits;
        # during recording all are.
        if self.isReadWorkerRunning or self.isStagedFocused:
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

    def SendPendingCommands(self, seconds):
        """Sends each DFM what it is waiting for, retrying for up to this many seconds, while no
        worker is running. Returns the DFMs still waiting."""
        deadline = time.monotonic() + seconds
        while True:
            waiting = [d for d in self.theDFMs.values() if d.DFMType==Enums.DFMTYPE.PLETCHERV3 and d.HasPendingCommands()]
            if not waiting or time.monotonic() >= deadline:
                return waiting
            for d in waiting:
                d.SendCommands()
            time.sleep(0.05)

    def _SendWaitingCommands(self):
        """Without a Program only the DFM on screen is read, so the others are sent what they are
        still waiting for here: the all-off instruction from the end of a Program, if they didn't
        take it then."""
        for d in list(self.theDFMs.values()):
            if(d is not self.activeDFM and d.DFMType==Enums.DFMTYPE.PLETCHERV3 and d.HasPendingCommands()):
                d.SendCommands()

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
        reportedErrors=set()
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
                # Packets being processed may not have been saved, and the DFM has already
                # dropped them, so this is an error. Each kind is reported once, so a fault that
                # repeats on every pass can't fill the message list.
                if(type(e).__name__ not in reportedErrors):
                    reportedErrors.add(type(e).__name__)
                    self.NewMessage(0, datetime.datetime.today(), 0, "Program worker error: {!r}".format(e), Enums.MESSAGETYPE.ERROR)
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
                tmp = None
            try:
                if(tmp is not None and tmp[-1].DFMID == self.activeDFM.ID):
                    self.theDFMs[tmp[-1].DFMID].ProcessPackets(tmp,False)
                    DFMGroup.DFMGroup_updatecomplete.notify()
                self._SendWaitingCommands()
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
                self.StartRecording()
            elif(self.currentProgram.IsAfterExperiment()):
                self.StopCurrentProgram()

            # No instructions until baselining is done, so thresholds are never partly baselined.
            if(self.currentProgram.IsDuringExperiment() and
               not any(d.isCalculatingBaseline for d in self.theDFMs.values())):
                self.UpdateDFMInstructions()

    def UpdateDFMInstructions(self):
        for d in self.theDFMs.values():
            # The thresholds sit above the baseline, so a DFM gets its instruction once that is done.
            if(d.isCalculatingBaseline):
                continue
            instruct, index, cycle = self.currentProgram.GetCurrentPosition(d.ID)
            d.UpdateInstruction(instruct,self.currentProgram.autoBaseline,index,cycle)
    #endregion

    #region Program Methods
    def LoadTextProgram(self,programPath):
        """Returns False if the file has a problem; currentProgram.loadError says what and where."""
        with open(programPath,encoding="utf-8-sig") as f:
            lines = f.readlines()
        return self.currentProgram.LoadProgram(lines,self.theDFMs)

    def LoadSimpleProgram(self,startTime,duration):
        self.currentProgram.CreateSimpleProgram(startTime,duration)

    def CheckProgramCompatibility(self):
        """Why the loaded Program can't run on the DFMs present: one line per DFM, or an empty
        list. Each DFM is checked against its own firmware (read at connection): ratio types and
        Acclimation need 4.0.0, and a 1.0.5 board also can't take the NonFeeding type or times
        above 65535 ms. A V2 (I2C) DFM runs the old settings, so only what needs 4.0.0 counts."""
        problems = []
        for ID, d in sorted(self.theDFMs.items()):
            if(d.DFMType==Enums.DFMTYPE.ENVMONV3):
                continue
            if(d.DFMType!=Enums.DFMTYPE.PLETCHERV3):
                needed = self.currentProgram.FirmwareNeeded(ID)
                if(needed):
                    problems.append("DFM {} is a V2 DFM, which can't run: {}".format(ID, "; ".join(needed)))
                continue
            if(COMM.UsesParadigmFirmware(d.firmwareVersion)):
                continue
            needed = self.currentProgram.FirmwareNeeded(ID, COMM.FirmwareVersionTuple(d.firmwareVersion))
            if(needed):
                problems.append("DFM {} (firmware {}) can't run: {}".format(ID, d.firmwareVersion, "; ".join(needed)))
        return problems

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
        # The read worker that follows serves the DFM on screen, so every DFM is sent its
        # all-off instruction now. One that doesn't take it is tried again from the read worker.
        for d in self.SendPendingCommands(PROGRAM_END_SECONDS):
            self.NewMessage(d.ID, datetime.datetime.today(), 0,
                            "DFM {} didn't acknowledge the all-off instruction at the end of the Program, so its LEDs "
                            "may still be running the last Interval. Still trying.".format(d.ID), Enums.MESSAGETYPE.ERROR)
        self.isStagedFocused=False
        self.currentProgram.isActive=False
        self.StartReadWorker()
        self.MP.SetFocusDFM(self.activeDFM.ID)
        DFMGroup.DFMGroup_programEnded.notify()

    def StageCurrentProgram(self):
        if(len(self.theDFMs)==0):
            return
        self.StopReadWorker()
        self.currentProgram.isActive=True
        # Baselining starts with the recording (see StartRecording).
        for d in self.theDFMs.values():
            d.ResetBaseline()
        self.SetFastProgramReadInterval()
        self.StartProgramWorker()
        # Until the start time only the DFM on screen is read, as with no program running, so its
        # live data stays current. StartRecording reads them all again.
        self.isStagedFocused=True
        self.MP.SetFocusDFM(self.activeDFM.ID)
    #endregion
