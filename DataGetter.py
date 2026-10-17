import datetime
import itertools
import multiprocessing
import queue
import threading
import time

import COMM
import EnvironmentalMonitor
import StatusPacket
from Enums import COBSRESULT, COMMANDTYPE, COMMTYPE, DFMTYPE, PROCESSEDPACKETRESULT, STATUSREQUESTTYPE

# The reader runs in a forked process that inherits this object's state. Python 3.14 makes
# forkserver the default on Linux, which would try to pickle the object instead.
_mp = multiprocessing.get_context("fork")


class MP_Command:
    def __init__(self,ctype,arg,requestID=None):
        self.commandType = ctype
        self.arguments=arg
        self.requestID=requestID
    def __str__(self):
        return str(self.commandType) + ":" + str(self.arguments)


class DFMInfo:
    def __init__(self,id,dfmtype):
        self.ID = id
        self.DFMType=dfmtype
    def __str__(self):
        return str(self.ID) + str(self.DFMType)
    def __repr__(self):
        return "ID= "+ str(self.ID) + " Type= " + str(self.DFMType)


class DataGetter:
    """Owns the DFM bus. All bus traffic happens in a separate reader process; the main process
    talks to it through command_q, answer_q (replies to requests) and data_q (status packets)."""

    def __init__(self):
        self.command_q=_mp.Queue()
        self.answer_q=_mp.Queue()
        self.data_q=_mp.Queue()
        self.requestLock = threading.Lock()
        self.requestIDs = itertools.count(1)
        self.theCOMM = None
        self.COMMType = None
        self.DFMInfos = []
        self.focalDFMs = []
        # Reader-process state, by DFM ID.
        self.bufferResetCounts = {}
        # When each DFM last acknowledged a buffer reset (time.monotonic()), which is when its
        # record 1 started.
        self.bufferResetTimes = {}
        self.firmwareVersions = {}
        # Counts the times the bus was closed, so a read round stops if that happens during it.
        self.busGeneration = 0
        # DFMs whose last status reply was full, so more packets are waiting on them.
        self.laggingDFMs = []
        self.refreshRate=0.25
        self.startTime = datetime.datetime.today()
        self.currentReadIndex=1
        self.isPaused = True
        self.getLatestStatusOnly=False
        self.EnvMonV3_Temperature=0.0
        self.EnvMonV3_Humidity=0.0
        self.EnvMonV3_LUX=0.0
        self.theEnvironmentalMonitor = EnvironmentalMonitor.EnvironmentalMonitor(5)
        # A daemon, so the app can exit without stopping it first.
        self.theReader = _mp.Process(target=self.ReadWorker, daemon=True)
        self.theReader.start()

    #region Functions that can be called from outside the process
    def _Request(self, commandType, arguments, timeout):
        """Runs a command in the reader process and returns its answer, or None on timeout."""
        with self.requestLock:
            requestID = next(self.requestIDs)
            self.command_q.put(MP_Command(commandType, arguments, requestID))
            deadline = time.monotonic() + timeout
            while True:
                try:
                    answerID, answer = self.answer_q.get(timeout=max(0, deadline - time.monotonic()))
                except queue.Empty:
                    print("get Answer timeout")
                    return None
                # Anything else is a late answer to an earlier request that timed out.
                if answerID == requestID:
                    return answer

    def _Command(self, commandType, arguments=''):
        self.command_q.put(MP_Command(commandType, arguments))

    def StopReading(self):
        self._Command(COMMANDTYPE.STOP_READING)
    def ClearQueues(self):
        self._Command(COMMANDTYPE.CLEAR_DATAMESSQ)
    def PauseReading(self):
        self._Command(COMMANDTYPE.PAUSE_READING)
    def ResumeReading(self):
        self._Command(COMMANDTYPE.RESUME_READING)
    def StartReading(self):
        self._Command(COMMANDTYPE.PAUSE_READING)
        self._Command(COMMANDTYPE.CLEAR_DATAMESSQ)
        self._Command(COMMANDTYPE.RESET_COUNTER)
        self._Command(COMMANDTYPE.RESUME_READING)
    def FindDFM(self,COMMType):
        return self._Request(COMMANDTYPE.FIND_DFM,[COMMType],20) or []
    ## These return True only if the DFM acknowledged the command.
    def SendBufferReset(self,ID):
        return self._Request(COMMANDTYPE.BUFFER_RESET,[ID],3) is True
    def SendInstructionDFMV2_0(self,ID,currentInstruction):
        return self._Request(COMMANDTYPE.INSTRUCTION_V2,[ID,currentInstruction],3) is True
    def SendInstructionDFMV1_0_5(self,ID,currentInstruction):
        return self._Request(COMMANDTYPE.INSTRUCTION_V1_0_5,[ID,currentInstruction],3) is True
    def SendParadigmInstruction(self,ID,currentInstruction,number,keepState):
        ## Firmware 4.0.0 and later.
        return self._Request(COMMANDTYPE.INSTRUCTION_PARADIGM,[ID,currentInstruction,number,keepState],3) is True
    def SendLinkage(self,ID,currentLinkage):
        return self._Request(COMMANDTYPE.LINKAGE,[ID,currentLinkage],3) is True
    def GetVersion(self,ID):
        ## Returns the version as bytes (b'1.0.5' if the DFM doesn't answer), or None if the
        ## replies were garbled or the request timed out.
        return self._Request(COMMANDTYPE.GET_VERSION,[ID],3)
    def SendFrequency(self,ID,frequency):
        self._Command(COMMANDTYPE.SEND_FREQ,[ID,frequency])
    def SendPulseWidth(self,ID,pulseWidth):
        self._Command(COMMANDTYPE.SEND_PW,[ID,pulseWidth])
    def SendDarkState(self,ID,val):
        self._Command(COMMANDTYPE.SEND_DARK,[ID,val])
    def SendOptoState(self,ID,os1,os2):
        self._Command(COMMANDTYPE.SEND_OPTOSTATE,[ID,os1,os2])
    def SetReadInterval(self,interval):
        self._Command(COMMANDTYPE.SET_REFRESHRATE,[interval])
    def SetFocusDFM(self,dfmid):
        self._Command(COMMANDTYPE.SET_FOCAL_DFM,[dfmid])
    def SetStatusRequestType(self,requestType):
        if(requestType==STATUSREQUESTTYPE.LATESTONLY):
            self._Command(COMMANDTYPE.SET_GET_LATESTSTATUS)
        else:
            self._Command(COMMANDTYPE.SET_GET_NORMALSTATUS)
    def SetStartTime(self):
        self._Command(COMMANDTYPE.SET_STARTTIME,[datetime.datetime.today()])
    #endregion

    # Remember that any variables set at the time of process forking can not be changed except
    # through a queue.
    #region Reader process
    def _CloseCOMM(self):
        if self.theCOMM is not None:
            try:
                self.theCOMM.Close()
            except Exception as e:
                print(f"Close COMM: {e!r}")
        self.theCOMM = None
        self.busGeneration += 1

    def FindDFMInternal(self,COMMType):
        self._CloseCOMM()
        if(COMMType==COMMTYPE.UART):
            self.theCOMM=COMM.UARTCOMM()
            self.refreshRate=0.3
            skippedIDs=()
        elif(COMMType==COMMTYPE.I2C):
            self.theCOMM=COMM.I2CCOMM()
            self.refreshRate=0.2
            skippedIDs=(24,88,89) # RTC, light sensor, humidity sensor
        else:
            return []
        self.COMMType = COMMType
        # The main process makes new DFM objects for what is found, so this starts over too.
        self.bufferResetCounts = {}
        self.bufferResetTimes = {}
        self.firmwareVersions = {}
        self.laggingDFMs = []
        found=[]
        for i in range(1,100):
            if i in skippedIDs:
                continue
            dfmType = self.theCOMM.PollSlave(i)
            if dfmType is not None:
                found.append(DFMInfo(i,dfmType))
            time.sleep(0.010)
        ## Read in descending order so an EnvMonV3 (ID 99) is read first each round. This
        ## keeps the environmental info tacked on to the DFM status packets as up to date as
        ## possible (although still being updated only every 5sec or so.) For finer
        ## environmental detail the user will need to look in the EnvMon file.
        self.DFMInfos = found[::-1]
        if(len(found)>0):
            self.focalDFMs = [found[0]] if COMMType==COMMTYPE.UART else found
            self.ClearQueuesInternal()
            self.currentReadIndex=1
            self.isPaused=False
        return found

    def ClearQueuesInternal(self):
        # The answer queue is left alone: requests skip answers that aren't theirs.
        try:
            while True:
                self.data_q.get_nowait()
        except queue.Empty:
            pass

    def _Answer(self, command, answer):
        self.answer_q.put((command.requestID, answer))

    def ProcessCommand(self):
        try:
            command=self.command_q.get(block=False)
        except queue.Empty:
            return False
        try:
            self._ExecuteCommand(command)
        except Exception as e:
            # Keep the reader alive, and don't leave the requester waiting for its timeout.
            print(f"Reader command failed ({command}): {e!r}")
            if command.requestID is not None:
                self._Answer(command, None)
        return True

    def _ExecuteCommand(self, command):
        commandType = command.commandType
        args = command.arguments
        if(commandType == COMMANDTYPE.FIND_DFM):
            self._Answer(command, self.FindDFMInternal(args[0]))
            self.theEnvironmentalMonitor.Initialize()
        elif(commandType==COMMANDTYPE.STOP_READING):
            self._CloseCOMM()
            self.DFMInfos = []
            self.refreshRate=0.25
            self.isPaused=True
        elif(commandType==COMMANDTYPE.PAUSE_READING):
            self.isPaused=True
        elif(commandType==COMMANDTYPE.RESUME_READING):
            self.isPaused=False
        elif(commandType==COMMANDTYPE.RESET_COUNTER):
            self.currentReadIndex=1
        elif(commandType==COMMANDTYPE.CLEAR_DATAMESSQ):
            self.ClearQueuesInternal()
        elif(commandType==COMMANDTYPE.SET_STARTTIME):
            self.startTime=args[0]
        elif(commandType==COMMANDTYPE.SET_REFRESHRATE):
            self.refreshRate = args[0]
        elif(commandType==COMMANDTYPE.SET_FOCAL_DFM):
            if(args[0]==0):
                self.focalDFMs = self.DFMInfos
            else:
                self.focalDFMs = [i for i in self.DFMInfos if i.ID==args[0]] or self.focalDFMs
        elif(commandType==COMMANDTYPE.BUFFER_RESET):
            self._Answer(command, self.BufferResetInternal(args[0]))
        elif(commandType==COMMANDTYPE.GET_VERSION):
            self._Answer(command, self._ReadVersion(args[0]))
        elif(commandType==COMMANDTYPE.LINKAGE):
            self._Answer(command, self.theCOMM.SendLinkage(args[0],args[1]))
        elif(commandType==COMMANDTYPE.INSTRUCTION_V1_0_5):
            self._Answer(command, self.theCOMM.SendInstructionDFMV1_0_5(args[0],args[1]))
        elif(commandType==COMMANDTYPE.INSTRUCTION_V2):
            self._Answer(command, self.theCOMM.SendInstructionDFMV2_0(args[0],args[1]))
        elif(commandType==COMMANDTYPE.INSTRUCTION_PARADIGM):
            self._Answer(command, self.theCOMM.SendParadigmInstruction(args[0],args[1],args[2],args[3]))
        elif(commandType==COMMANDTYPE.SEND_DARK):
            self.theCOMM.SendDark(args[0],args[1])
        elif(commandType==COMMANDTYPE.SEND_FREQ):
            self.theCOMM.SendFrequency(args[0],args[1])
        elif(commandType==COMMANDTYPE.SEND_PW):
            self.theCOMM.SendPulseWidth(args[0],args[1])
        elif(commandType==COMMANDTYPE.SEND_OPTOSTATE):
            self.theCOMM.SendOptoState(args[0],args[1],args[2])
        elif(commandType==COMMANDTYPE.SET_GET_LATESTSTATUS):
            self.getLatestStatusOnly=True
        elif(commandType==COMMANDTYPE.SET_GET_NORMALSTATUS):
            self.getLatestStatusOnly=False
        else:
            print("Unknown Command")

    def BufferResetInternal(self,ID):
        isReset = self.theCOMM.RequestBufferReset(ID)
        if isReset:
            # Reads are tagged with this count, so the main process can tell reads of the old
            # buffer that are still queued from reads of the new one.
            self.bufferResetCounts[ID] = self.bufferResetCounts.get(ID,0)+1
            self.bufferResetTimes[ID] = time.monotonic()
        return isReset

    def _ReadVersion(self,ID):
        """Asks a DFM for its firmware version and keeps it, as it decides the record size. Only
        firmware 1.0.5, which has no version request, is expected not to answer, so a board
        already known to run a later version keeps it when a request goes unanswered. Returns the
        version, or None if every reply was garbled."""
        version = self.theCOMM.GetVersion(ID)
        known = self.firmwareVersions.get(ID)
        if(version == COMM.LEGACY_VERSION and known not in (None, COMM.LEGACY_VERSION)):
            print(f"No answer to the version request ({ID}); keeping {known!r}")
            return known
        if(version is not None):
            self.firmwareVersions[ID] = version
        return version

    def _RecheckRecordSize(self,info,size):
        """Called when a reply isn't a whole number of the records expected. If it is a whole
        number of the other size, the firmware version was misread (for example a 4.0.0 board
        whose version reply was lost, taken for 1.0.5), so it is read again. Returns True if the
        record size changed."""
        other = StatusPacket.V3_PACKET_SIZE if self._RecordSize(info) == StatusPacket.V4_PACKET_SIZE else StatusPacket.V4_PACKET_SIZE
        if(info.DFMType != DFMTYPE.PLETCHERV3 or size == 0 or size % other != 0):
            return False
        print(f"Records from {info.ID} are {other} bytes; reading its firmware version again")
        # The record size shows the known version is wrong, so an unanswered request counts.
        self.firmwareVersions.pop(info.ID, None)
        self._ReadVersion(info.ID)
        return self._RecordSize(info) == other

    def ReadWorker(self):
        commandsInARow=0
        lastTime = time.time()
        lastTime_Env = time.time()
        while(True):
            # Commands go first, but no more than 13 in a row so reading isn't starved.
            if(commandsInARow<=12 and self.ProcessCommand()):
                commandsInARow+=1
            else:
                commandsInARow=0
                if(self.isPaused==False):
                    if(time.time()-lastTime>self.refreshRate):
                        lastTime = time.time()
                        self.ReadRound()
                    elif(self.laggingDFMs):
                        # Read these again now rather than next round, so a backlog drains
                        # instead of growing. Commands still get a turn between reads.
                        self.ReadValues([i for i in self.focalDFMs if i in self.laggingDFMs])
                if(time.time()-lastTime_Env>1):
                    self.theEnvironmentalMonitor.StepMonitor()
                    lastTime_Env = time.time()
            time.sleep(0.002)

    def ReadRound(self):
        """Reads every focal DFM once."""
        self.EnvMonV3_Temperature=0.0
        self.EnvMonV3_Humidity=0.0
        self.EnvMonV3_LUX=0.0
        self.ReadValues(self.focalDFMs)

    def ReadValues(self,infos):
        currentTime = datetime.datetime.today()
        generation = self.busGeneration
        lagging = []
        for info in infos:
            try:
                result,payload=self.theCOMM.GetStatusPacket(info.ID,info.DFMType,self.getLatestStatusOnly,self._RecordSize(info))
                readTime = time.monotonic()
                packList=self.ProcessPacket(info,result,payload,currentTime)
                recordSize = self._RecordSize(info)
                maxRecords = COMM.MAX_STATUS_PACKETS_V4 if recordSize == StatusPacket.V4_PACKET_SIZE else COMM.MAX_STATUS_PACKETS
                isFull = len(payload) >= maxRecords*recordSize
                resetCount = self.bufferResetCounts.get(info.ID,0)
                resetTime = self.bufferResetTimes.get(info.ID)
                for p in packList:
                    p.bufferResetCount = resetCount
                    p.isFullReply = isFull
                    p.secondsSinceReset = None if resetTime is None else readTime - resetTime
                    p.readTime = readTime
                # Queued before the ACK: if the ACK fails the DFM just sends the packets again.
                self.data_q.put(packList)
                self._Acknowledge(info,packList)
                if(isFull):
                    lagging.append(info)
            except Exception as e:
                print(f"Get status exception ({info.ID}): {e!r}")
            time.sleep(0.002)
            # Commands go out between reads, so an instruction waits for one DFM's read, not for
            # the whole round (which grows with every DFM, and by 2 s for each that doesn't answer).
            for _ in range(13):
                if not self.ProcessCommand():
                    break
            if(self.isPaused or self.busGeneration != generation):
                break
        self.laggingDFMs = lagging

    def _Acknowledge(self,info,packList):
        """A V3 DFM drops the packets it sent once they are ACKed, so only packets that were read
        correctly are acknowledged. The read stops at the first bad packet."""
        numGood = sum(1 for _ in itertools.takewhile(lambda p: p.processResult == PROCESSEDPACKETRESULT.OKAY, packList))
        if(numGood == len(packList)):
            # A plain ACK: the firmware counts any partial ACK, even one naming every packet, as
            # a missed ACK and sets the No Ack error bit.
            self.theCOMM.SendAck(info.ID)
        elif(numGood > 0 and info.DFMType == DFMTYPE.PLETCHERV3 and
             COMM.SupportsPartialAck(self.firmwareVersions.get(info.ID, b""))):
            # The good packets are kept, so the DFM need only send the rest again.
            self.theCOMM.SendPartialAck(info.ID, packList[numGood-1].recordIndex)

    def _RecordSize(self,info):
        """Status record size: 127 bytes from DFM firmware 4.0.0, 56 before (and for the EnvMon)."""
        if(info.DFMType==DFMTYPE.PLETCHERV3 and COMM.UsesParadigmFirmware(self.firmwareVersions.get(info.ID, b""))):
            return StatusPacket.V4_PACKET_SIZE
        return StatusPacket.V3_PACKET_SIZE

    def _FailedPacket(self,info,result):
        packet=StatusPacket.StatusPacket(0,info.ID,info.DFMType)
        packet.processResult = result
        return [packet]

    def ProcessPacket(self,info,result,bytesData,currentTime):
        """Turns one read into a non-empty list of status packets."""
        if(result==COBSRESULT.NOANSWER):
            print(f"No answer: {info.ID}")
            return self._FailedPacket(info,PROCESSEDPACKETRESULT.NOANSWER)
        if(result!=COBSRESULT.OKAY):
            print("Incomplete packet")
            return self._FailedPacket(info,PROCESSEDPACKETRESULT.INCOMPLETEPACKET)
        if(info.DFMType!=DFMTYPE.PLETCHERV3 and info.DFMType!=DFMTYPE.ENVMONV3):
            currentStatusPacket = StatusPacket.StatusPacket(self.currentReadIndex,info.ID,info.DFMType)
            currentStatusPacket.ProcessStatusPacket(bytesData,currentTime)
            if(self.theEnvironmentalMonitor.isPresent):
                currentStatusPacket.AddEnvironmentalInformation(self.theEnvironmentalMonitor.temperature,self.theEnvironmentalMonitor.light,self.theEnvironmentalMonitor.humidity)
            self.currentReadIndex+=1
            return [currentStatusPacket]

        recordSize = self._RecordSize(info)
        numPacketsReceived, extraBytes = divmod(len(bytesData),recordSize)
        if((numPacketsReceived==0 or extraBytes!=0) and self._RecheckRecordSize(info,len(bytesData))):
            recordSize = self._RecordSize(info)
            numPacketsReceived, extraBytes = divmod(len(bytesData),recordSize)
        if(numPacketsReceived==0 or extraBytes!=0):
            print("Wrong num bytes: " + str(len(bytesData)/recordSize))
            return self._FailedPacket(info,PROCESSEDPACKETRESULT.WRONGNUMBYTES)
        currentStatusPackets=[]
        for i in range(0,numPacketsReceived):
            tmpPacket = StatusPacket.StatusPacket(self.currentReadIndex,info.ID,info.DFMType)
            # This gets the startTime of the experiment.  The others get the time of the packet
            tmpPacket.ProcessStatusPacket(bytesData,self.startTime,i,recordSize)
            if(info.DFMType==DFMTYPE.ENVMONV3):
                ## This works here because the EnvMon will always be called first each round of read values.
                self.EnvMonV3_Temperature=tmpPacket.temp
                self.EnvMonV3_Humidity=tmpPacket.humidity
                self.EnvMonV3_LUX=tmpPacket.lux
            else:
                tmpPacket.AddEnvironmentalInformation(self.EnvMonV3_Temperature,self.EnvMonV3_LUX,self.EnvMonV3_Humidity)
            currentStatusPackets.append(tmpPacket)
            self.currentReadIndex+=1
            if(tmpPacket.processResult!=PROCESSEDPACKETRESULT.OKAY):
                # Without an ACK the DFM resends this packet and the ones after it. Recording the
                # later ones now would get the resent copy of this one discarded as a repeat.
                break
        return currentStatusPackets
    #endregion
