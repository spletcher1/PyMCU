import array
import collections
import datetime
import random
import time

import COMM
import DataBuffer
import DFMErrors
import Enums
import Event
import Instruction
import Message
import OptoLid
import StatusPacket

# Seconds to wait before retrying commands that a DFM did not acknowledge.
COMMAND_RETRY_INTERVAL = 1.0
# A command that fails this many times in a row, or is still waiting after this many seconds,
# is reported as an error.
COMMAND_FAILURES_REPORTED = 3
COMMAND_WAIT_REPORTED = 10.0
# A DFM applies an instruction when it arrives, so a record read this long after the ACK shows it.
INSTRUCTION_APPLY_SECONDS = 0.5
# Times an instruction is sent again because the DFM's records showed another one.
MAX_INSTRUCTION_RESENDS = 3

def UsesV2Instructions(version):
    # Firmware 2.0.0 and later take 4-byte decay, delay and max time on.
    return COMM.FirmwareVersionTuple(version) >= (2, 0, 0)

# Message and new status for each kind of failed read.
READ_FAILURES = {
    Enums.PROCESSEDPACKETRESULT.CHECKSUMERROR: ("Checksum mismatch", Enums.CURRENTSTATUS.ERROR),
    Enums.PROCESSEDPACKETRESULT.NOANSWER: ("No answer", Enums.CURRENTSTATUS.MISSING),
    Enums.PROCESSEDPACKETRESULT.WRONGNUMBYTES: ("Packet size mismatch", Enums.CURRENTSTATUS.ERROR),
    Enums.PROCESSEDPACKETRESULT.INCOMPLETEPACKET: ("Incomplete packet received", Enums.CURRENTSTATUS.ERROR),
}

# What an instruction number stood for: the Interval index (from 0) and Cycle, or None for
# instructions outside the Program (idle, outputs on).
InstructionInfo = collections.namedtuple("InstructionInfo", "index cycle instruction")
# Instruction numbers remembered, for records that arrive after later instructions were sent.
INSTRUCTION_HISTORY = 256
# Records held after a restart before they are stored anyway (a DFM holds 780).
MAX_RESTART_PACKETS = 2000


def ResendWindow(sp):
    """A DFM sends again only the records of its last reply that weren't acknowledged, so a record
    repeated from further back than this can't be a resend: the DFM restarted and its count began
    again. Two replies' worth, to be safe."""
    return 2*(COMM.MAX_STATUS_PACKETS_V4 if sp.isV4 else COMM.MAX_STATUS_PACKETS)

class DFM:
    DFM_message = Event.Event()
    #region Initialization, etc.
    def __init__(self,id,dfmType,mp):
        self.MP = mp
        self.ID=id
        self.DFMType = dfmType
        ## Firmware 1.0.5 until the version is read. Those boards don't answer the request, so
        ## this is also what they end up with.
        self.DFMSubType = Enums.DFMSUBTYPE.V1_0_5
        self.outputFile = "DFM" + str(self.ID) + "_0.csv"
        self.outputFileIncrementor=0
        self.status = Enums.CURRENTSTATUS.UNDEFINED
        self.pastStatus = Enums.PASTSTATUS.ALLCLEAR
        self.theData = DataBuffer.DataBuffer()
        self.sampleIndex=1
        self.lastDFMIndex=0
        # Buffer resets seen in the reads so far (see StatusPacket.bufferResetCount).
        self.bufferResetCount=0
        self.signalBaselines=array.array("i",(0 for i in range(0,12)))
        self.currentLinkage = array.array("i",[1,2,3,4,5,6,7,8,9,10,11,12])
        self.baselineSamples=0
        self.isCalculatingBaseline=False
        self.currentInstruction = Instruction.DFMInstruction()
        self.currentPosition = (None, None)
        # Firmware 4.0.0 repeats the number of the instruction in use in every record. Starting
        # at a random number makes a number left over from an earlier run unlikely to match.
        self.instructionNumber = random.randint(1, 0xFFFF)
        self.instructionInfo = collections.OrderedDict()
        self.lastSentParadigmName = None
        # Activation totals carried past the DFM's 16-bit count.
        self.lastActivationsRaw = [0]*12
        # Whether a record from a Program Interval has arrived since the last buffer reset; the
        # records before it (the baseline) are written as Interval 0.
        self.programRecordSeen = False
        self.activationTotals = [0]*12
        # Added to the DFM's record indexes after it restarted on its own, so Index and the record
        # times carry on (see _FinishRestart); the records held until then, or None.
        self.indexOffset = 0
        self.restartPackets = None
        self.restartLastIndex = 0
        # The first and last records lost while the data buffer was full, and how many.
        self.droppedFirst = None
        self.droppedLast = None
        self.droppedCount = 0
        # Kinds of packet-processing error already reported, so a repeating fault reports once.
        self.reportedPacketErrors = set()
        self.lastParadigmPacket = None
        self.isInstructionUpdateNeeded=False
        # Set by SetOutputsOn (Toggle Outputs), cleared by any other instruction.
        self.isOutputsOn=False
        # The number of the last instruction the DFM acknowledged and when (time.monotonic()), and
        # how often it was sent again because the DFM's records showed another one.
        self.ackedInstructionNumber=None
        self.ackedInstructionTime=0.0
        self.instructionResends=0
        # Commands that keep failing: name -> [since (time.monotonic()), failures, reported].
        self.commandTrouble={}
        self.isBufferResetNeeded=False
        # This is true because we need to get this ASAP for each DFM upon connection.
        self.isVersionGetNeeded = True
        self.isLinkageSetNeeded=False
        # True after a version request that a 1.0.5 board didn't answer (see UpdateReportedValues).
        self.maskProbeError = False
        # The error byte of the last record, so each error is reported when it appears.
        self.lastErrorFlags = 0
        self.retryTime=0.0
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV3):
            # Narrowed down once the firmware version is known.
            self.currentDFMErrors = DFMErrors.DFMErrors(DFMErrors.V3_ERROR_DISPLAY_BEFORE_3_5_0)
        else:
            self.currentDFMErrors = DFMErrors.DFMErrors()
        self.reportedOptoFrequency=0
        self.reportedOptoPulsewidth=0
        self.reportedOptoStateCol1=0
        self.reportedOptoStateCol2=0
        self.reportedTemperature=1.0
        self.reportedDarkState = Enums.DARKSTATE.OFF
        self.reportedHumidity=1.0
        self.reportedLUX=0
        self.reportedVoltsIn=1.0
        self.firmwareVersion="0.0.0"
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV2):
            self.theOptoLid = OptoLid.OptoLid()

    def __str__(self):
        return "DFM " + str(self.ID)

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        DFM.DFM_message.notify(tmp)
    #endregion

    #region Property-like getters and setters
    def SetLinkage(self,links):
        self.currentLinkage = links
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV2):
            self.theOptoLid.SetLinkage(self.currentLinkage)
        self.isLinkageSetNeeded = True

    def GetDFMName(self):
        return "DFM "+str(self.ID)

    def GetLastAnalogData(self,adjustForBaseline):
        tmp = self.theData.GetLastDataPoint()
        if(tmp.sample==0):
            return None
        if(adjustForBaseline == False):
            return tmp.analogValues
        resultArray=array.array("i",(0 for i in range(0,12)))
        for i in range(0,12):
            resultArray[i]=max(tmp.analogValues[i]-self.signalBaselines[i],0)
        return resultArray

    def SetIdleStatus(self):
        ## Idle: every Well Off.
        self._SetInstruction(Instruction.DFMInstruction())

    def SetOutputsOn(self):
        instruct = Instruction.DFMInstruction()
        instruct.SetOptoValues([Instruction.ON]*12)
        self._SetInstruction(instruct)
        self.isOutputsOn = True

    def SetOutputsOff(self):
        self.SetIdleStatus()

    def SetStatus(self, newStatus):
        if(newStatus != self.status):
            if(newStatus == Enums.CURRENTSTATUS.ERROR or newStatus == Enums.CURRENTSTATUS.MISSING):
                self.pastStatus = Enums.PASTSTATUS.PASTERROR
            self.status = newStatus
    #endregion

    #region Baselining
    def ResetBaseline(self):
        for i in range(0,len(self.signalBaselines)):
            self.signalBaselines[i]=0
        self.baselineSamples=0
        self.isCalculatingBaseline = False
    def UpdateBaseline(self):
        last = self.GetLastAnalogData(False)
        if last is None:
            return
        for i in range(0,12):
            tmp = self.signalBaselines[i] * self.baselineSamples
            self.signalBaselines[i] = int((tmp + last[i])/(self.baselineSamples+1))
        self.baselineSamples = self.baselineSamples+1
        if (self.baselineSamples>=10):
            self.isCalculatingBaseline=False
    def BaselineDFM(self):
        self.ResetBaseline()
        self.isCalculatingBaseline = True
    #endregion

    #region Packet processing, reading, writing, file methods.
    def UpdateReportedValues(self, currentStatusPackets, isRecording):
        last = currentStatusPackets[-1]
        self.reportedHumidity = last.humidity
        self.reportedLUX = last.lux
        self.reportedTemperature = last.temp
        self.reportedOptoFrequency = last.optoFrequency
        self.reportedOptoPulsewidth = last.optoPulseWidth
        self.reportedOptoStateCol1  = last.optoState1
        self.reportedOptoStateCol2 = last.optoState2
        self.reportedVoltsIn = last.voltsIn
        if(last.darkStatus==0):
            self.reportedDarkState = Enums.DARKSTATE.OFF
        else:
            self.reportedDarkState = Enums.DARKSTATE.ON
        if(last.isV4):
            self.lastParadigmPacket = last

        for sp in currentStatusPackets:
            if(sp.processResult != Enums.PROCESSEDPACKETRESULT.OKAY):
                continue
            errorFlags = sp.errorFlags
            if(self.maskProbeError and errorFlags & DFMErrors.P_TYPE_MASK):
                # Firmware 1.0.5 flags the version request as an unknown command. That isn't the
                # DFM's fault, so the one record that reports it is cleaned up and the box stays clear.
                errorFlags &= ~DFMErrors.P_TYPE_MASK
                self.maskProbeError = False
            if not isRecording:
                # Packets aren't kept then, so an overflow loses nothing. It is also certain
                # when the MCU asks for the latest packet only, as nothing drains the buffer.
                errorFlags &= ~DFMErrors.OVERFLOW_MASK
            self.currentDFMErrors.UpdateErrors(errorFlags)
            # Each error is reported when it appears, not again for every record that still has it.
            for bit in range(0,8):
                if(errorFlags & ~self.lastErrorFlags & (1<<bit)):
                    self._ReportErrorBit(sp,bit)
            self.lastErrorFlags = errorFlags

    def _ReportErrorBit(self,sp,bit):
        if(bit == 1 and self.currentDFMErrors.display is DFMErrors.V3_ERROR_DISPLAY):
            # Firmware 3.5.0 and later: records were overwritten on the DFM, so they are gone.
            self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,
                            "DFM {}'s record buffer overflowed: records were overwritten before they could be read, so data was lost.".format(self.ID),
                            Enums.MESSAGETYPE.ERROR)
            return
        label = DFMErrors.BitLabel(self.currentDFMErrors.display,bit)
        text = "DFM {} error: {}".format(self.ID,"bit {}".format(bit) if label is None else
                                          (label[0] if not label[1] else "{} ({})".format(label[0],label[1].rstrip("."))))
        self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,text,Enums.MESSAGETYPE.NOTICE)

    def ProcessPackets(self,currentStatusPackets,saveDataToQueue):
        # V3 DFMs resend packets that were not ACKed, so a failed read is only a notice for them.
        if (self.DFMType == Enums.DFMTYPE.PLETCHERV3):
            theMessageType =  Enums.MESSAGETYPE.NOTICE
        else:
            theMessageType =  Enums.MESSAGETYPE.ERROR
        # Indexes start again at 1 with the first read after a buffer reset. This is done here,
        # not when the reset is ACKed, because reads made before the reset may still be queued
        # behind it; with the index already back at 0 they would make every later packet look
        # repeated.
        if(currentStatusPackets[0].bufferResetCount != self.bufferResetCount):
            self.bufferResetCount = currentStatusPackets[0].bufferResetCount
            self.sampleIndex=1
            self.lastDFMIndex=0
            # A buffer reset also restarts the DFM's Activation counts.
            self.lastActivationsRaw = [0]*12
            self.activationTotals = [0]*12
            self.programRecordSeen = False
            self.indexOffset = 0
            self.restartPackets = None
        newPackets=[]
        repeated=[]
        for sp in currentStatusPackets:
            # Each packet on its own: the DFM has already dropped them, so one that can't be
            # processed mustn't take the rest of the read with it.
            try:
                self._ProcessPacket(sp,saveDataToQueue,theMessageType,newPackets,repeated)
            except Exception as e:
                print(f"Packet processing exception ({self.ID}): {e!r}")
                if(type(e).__name__ not in self.reportedPacketErrors):
                    self.reportedPacketErrors.add(type(e).__name__)
                    self.NewMessage(self.ID,datetime.datetime.today(),sp.recordIndex,"Record {} couldn't be processed and was lost: {!r}".format(sp.recordIndex,e),Enums.MESSAGETYPE.ERROR)
        if(repeated):
            # The DFM didn't get the last ACK and sent those records again. They were saved the
            # first time, so nothing is lost: one notice per read.
            self.NewMessage(self.ID,repeated[0].packetTime,repeated[0].recordIndex,
                            "Records {} were sent again after a missed ACK; they were already saved.".format(
                                self._RecordRange(repeated[0].recordIndex,repeated[-1].recordIndex)),
                            Enums.MESSAGETYPE.NOTICE)
        self._CheckRunningInstruction(currentStatusPackets)
        # After a restart the records wait until a reply that held everything the DFM had,
        # whose newest record shows how far the DFM's count is behind.
        if(self.restartPackets is not None):
            last = currentStatusPackets[-1]
            isComplete = all(p.processResult == Enums.PROCESSEDPACKETRESULT.OKAY for p in currentStatusPackets)
            if((isComplete and not last.isFullReply and last.secondsSinceReset is not None)
                    or len(self.restartPackets) > MAX_RESTART_PACKETS):
                self._FinishRestart(last.secondsSinceReset)

        # Only packets seen for the first time are reported, so each packet's error flags count
        # once. Resent packets were counted when they first came, and with partial ACKs the good
        # packets before a bad one aren't sent again.
        if(newPackets):
            self.UpdateReportedValues(newPackets,saveDataToQueue)
        self.CheckStatus()

    def _ProcessPacket(self,sp,saveDataToQueue,theMessageType,newPackets,repeated):
        if(sp.processResult != Enums.PROCESSEDPACKETRESULT.OKAY):
            if(sp.processResult in READ_FAILURES):
                text, newStatus = READ_FAILURES[sp.processResult]
                self.SetStatus(newStatus)
                self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,text,theMessageType)
        elif(sp.recordIndex<=0):
            # It's okay now to receive these because of the fast buffer reset and call. I will not call this an error.
            print("({:d}) Empty packet received".format(self.ID))
        elif(saveDataToQueue and sp.recordIndex <= self.lastDFMIndex - ResendWindow(sp)):
            self._StartRestart(sp)
            self._AcceptPacket(sp,saveDataToQueue,newPackets)
        elif(sp.recordIndex<=self.lastDFMIndex):
            # Sent again; not added to the data file twice.
            repeated.append(sp)
        else:
            self._AcceptPacket(sp,saveDataToQueue,newPackets)

    def _AcceptPacket(self,sp,saveDataToQueue,newPackets):
        """A packet seen for the first time: checked against the last index, then stored, or held
        while the DFM's count is worked out after a restart."""
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV3 and not self.isVersionGetNeeded
                and sp.isV4 != COMM.UsesParadigmFirmware(self.firmwareVersion)):
            # The reader read the version again when the record size gave it away; this DFM
            # object still has the old one, which decides the instruction format.
            self.NewMessage(self.ID,datetime.datetime.today(),sp.recordIndex,
                            "DFM {} sent {} records, but its firmware was read as {}. Reading its version again.".format(
                                self.ID,"4.0.0" if sp.isV4 else "pre-4.0.0",self.firmwareVersion),Enums.MESSAGETYPE.NOTICE)
            self.isVersionGetNeeded = True
        newPackets.append(sp)
        if(saveDataToQueue and self.DFMType==Enums.DFMTYPE.PLETCHERV3):
            if(sp.recordIndex != (self.lastDFMIndex+1)):
                self._ReportLostRecords(sp)
                self.SetStatus(Enums.CURRENTSTATUS.ERROR)
            self.lastDFMIndex = sp.recordIndex
        if(self.restartPackets is not None):
            self.restartPackets.append(sp)
        else:
            self._AddPacket(sp,saveDataToQueue)

    def _RecordRange(self,first,last):
        """'Index a to b' as the data file numbers the DFM's records a to b. While a restart's
        offset isn't known yet, the DFM's own count is given."""
        if(self.restartPackets is not None):
            return "{} to {} (counted from the DFM's restart)".format(first,last)
        first, last = first+self.indexOffset, last+self.indexOffset
        return "Index {}".format(first) if first==last else "Index {} to {}".format(first,last)

    def _ReportLostRecords(self,sp):
        """The DFM's records jumped from lastDFMIndex to sp.recordIndex: the ones between never
        arrived, typically overwritten on the DFM while reads fell behind."""
        count = sp.recordIndex-self.lastDFMIndex-1
        if(count <= 0):
            return
        seconds = count*StatusPacket.V3_PACKET_INTERVAL
        start = sp.packetTime-datetime.timedelta(seconds=seconds)
        if(self.indexOffset and self.restartPackets is None):
            start += datetime.timedelta(seconds=self.indexOffset*StatusPacket.V3_PACKET_INTERVAL)
        self.NewMessage(self.ID,start,sp.recordIndex,
                        "Lost {} record{} ({:.1f} s): {}, from {}.".format(
                            count,"" if count==1 else "s",seconds,
                            self._RecordRange(self.lastDFMIndex+1,sp.recordIndex-1),start.strftime("%H:%M:%S")),
                        Enums.MESSAGETYPE.ERROR)

    def _StartRestart(self,sp):
        """The DFM restarted (a brown-out or watchdog reset): its record count began again at 1
        without a buffer reset from the MCU, and it lost its instruction, linkage and Paradigm
        state. Its records are held until the count's new offset is known (_FinishRestart)."""
        self.restartLastIndex = self.lastDFMIndex + self.indexOffset
        self.NewMessage(self.ID,datetime.datetime.today(),sp.recordIndex,
                        "DFM {} restarted: its record count went back from {} to {}. Its Paradigm state and Activation "
                        "counts started again. Sending its Interval and linkage again.".format(self.ID,self.lastDFMIndex,sp.recordIndex),
                        Enums.MESSAGETYPE.ERROR)
        self.restartPackets = []
        self.lastDFMIndex = 0
        # The Activation totals carry on from where they were.
        self.lastActivationsRaw = [0]*12
        self.lastSentParadigmName = None
        self.isInstructionUpdateNeeded = True
        self.isLinkageSetNeeded = True

    def _FinishRestart(self,secondsSinceReset):
        """Stores the records held since a restart. Their Index and time continue from the
        recording's: secondsSinceReset is when the read holding the newest of them was made,
        counted from the buffer reset that started the recording, so it says what the index
        would have been. Without it they follow straight on from the last record."""
        firstIndex = self.restartPackets[0].recordIndex if self.restartPackets else 1
        offset = self.restartLastIndex
        if(secondsSinceReset is not None):
            offset = max(offset, round(secondsSinceReset/StatusPacket.V3_PACKET_INTERVAL) - self.lastDFMIndex)
        self.indexOffset = offset
        lost = offset + firstIndex - self.restartLastIndex - 1
        if(lost > 0):
            self.NewMessage(self.ID,datetime.datetime.today(),self.restartLastIndex,
                            "DFM {} recorded nothing for about {:.0f} s while it restarted: Index {} to {} are missing.".format(
                                self.ID,lost*StatusPacket.V3_PACKET_INTERVAL,self.restartLastIndex+1,self.restartLastIndex+lost),
                            Enums.MESSAGETYPE.ERROR)
        packets, self.restartPackets = self.restartPackets, None
        for sp in packets:
            self._AddPacket(sp,True)

    def FlushPendingRecords(self):
        """Stores records still held after a restart, when the recording ends."""
        if(self.restartPackets is not None):
            self._FinishRestart(None)

    def _AddParadigmState(self,sp):
        """Adds what the record's instruction number stands for (Interval, Cycle, Paradigm, light
        settings) and the Activation totals, carried past the DFM's 16-bit count."""
        if not sp.isV4:
            return
        info = self.instructionInfo.get(sp.instructionNumber)
        if info is not None:
            sp.interval = info.index
            sp.cycle = info.cycle
            sp.paradigmName = info.instruction.paradigm.name
            sp.optoFrequency = info.instruction.paradigm.frequency
            sp.optoPulseWidth = info.instruction.paradigm.pulseWidth
            sp.darkStatus = info.instruction.theDarkState.value
        if info is not None and info.index is not None:
            self.programRecordSeen = True
        sp.isBeforeProgram = not self.programRecordSeen
        for w in range(0,12):
            self.activationTotals[w] += (sp.activationsRaw[w] - self.lastActivationsRaw[w]) & 0xFFFF
            self.lastActivationsRaw[w] = sp.activationsRaw[w]
        sp.activationTotals = list(self.activationTotals)

    def _AddPacket(self,sp,saveDataToQueue):
        # After a restart the DFM's count is behind the recording's (see _FinishRestart).
        if(self.indexOffset):
            sp.recordIndex += self.indexOffset
            sp.packetTime += datetime.timedelta(seconds=self.indexOffset*StatusPacket.V3_PACKET_INTERVAL)
        self._AddParadigmState(sp)
        sp.sample = self.sampleIndex
        if(self.theData.NewData(sp,saveDataToQueue)==False):
            # The data file can't be written and the buffer is full. One message when it starts
            # and one with what was lost when it ends, rather than one per record.
            if(self.droppedFirst is None):
                self.droppedFirst, self.droppedCount = sp, 0
                self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,
                                "DFM {}'s data buffer is full because its data file can't be written: its records are being lost.".format(self.ID),
                                Enums.MESSAGETYPE.ERROR)
            self.droppedLast = sp
            self.droppedCount += 1
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
        else:
            if(self.droppedFirst is not None):
                first, last = self.droppedFirst, self.droppedLast
                self.NewMessage(self.ID,last.packetTime,last.recordIndex,
                                "DFM {} lost {} records while its data buffer was full: Index {} to {}, {} to {}.".format(
                                    self.ID,self.droppedCount,first.recordIndex,last.recordIndex,
                                    first.packetTime.strftime("%H:%M:%S"),last.packetTime.strftime("%H:%M:%S")),
                                Enums.MESSAGETYPE.ERROR)
                self.droppedFirst = None
            if(saveDataToQueue):
                self.sampleIndex+=1
                self.SetStatus(Enums.CURRENTSTATUS.RECORDING)
            else:
                self.SetStatus(Enums.CURRENTSTATUS.READING)
        if(self.isCalculatingBaseline):
            self.UpdateBaseline()

    def ResetOutputFileStuff(self):
        self.outputFileIncrementor=0
        self.outputFile="DFM" + str(self.ID) + "_0.csv"

    def IncrementOutputFile(self):
        self.outputFileIncrementor+=1
        self.outputFile="DFM" + str(self.ID) + "_"+str(self.outputFileIncrementor)+".csv"
    #endregion

    #region Updating
    def UpdateInstruction(self,instruct,useBaseline,index=None,cycle=None):
        """Starts sending the Program's instruction for an Interval (index from 0) in a Cycle. It is
        sent again when the Interval or Cycle changes, even if the instruction itself doesn't."""
        # There is no instruction before a program starts; keep the current one.
        if(instruct is None or (instruct is self.currentInstruction and (index,cycle) == self.currentPosition)):
            return
        if(useBaseline):
            instruct.SetBaseline(self.signalBaselines)
        self._SetInstruction(instruct,index,cycle)

    def _SetInstruction(self,instruct,index=None,cycle=None):
        self.isOutputsOn = False
        self.currentInstruction = instruct
        self.currentPosition = (index,cycle)
        self.instructionNumber = self.instructionNumber % 0xFFFF + 1
        self.instructionInfo[self.instructionNumber] = InstructionInfo(index,cycle,instruct)
        while len(self.instructionInfo) > INSTRUCTION_HISTORY:
            self.instructionInfo.popitem(last=False)
        self.isInstructionUpdateNeeded=True

    def GetCurrentParadigmState(self):
        """For the DFM page: (Paradigm name, type name, Interval from 1 or None, Cycle or None, the
        last record with Paradigm state or None)."""
        paradigm = self.currentInstruction.paradigm
        index, cycle = self.currentPosition
        return (paradigm.name, paradigm.typeName, None if index is None else index+1, cycle,
                self.lastParadigmPacket)

    def CheckStatus(self):
        if(self.DFMType == Enums.DFMTYPE.PLETCHERV3):
            self.CheckStatusV3()
        elif(self.DFMType == Enums.DFMTYPE.PLETCHERV2):
            self.CheckStatusV2()
        else:
            pass #Sable V2 doesn't need anything here.

    def CheckStatusV2(self):
        if self.status == Enums.CURRENTSTATUS.MISSING or self.status == Enums.CURRENTSTATUS.ERROR or self.status == Enums.CURRENTSTATUS.UNDEFINED:
            return
        lsp = self.theData.GetLastDataPoint()

        if(lsp.optoFrequency!=self.currentInstruction.frequency):
            self.MP.SendFrequency(self.ID,self.currentInstruction.frequency)

        if(lsp.optoPulseWidth!=self.currentInstruction.pulseWidth):
            self.MP.SendPulseWidth(self.ID,self.currentInstruction.pulseWidth)

        if(lsp.darkStatus!=self.currentInstruction.theDarkState.value):
            self.MP.SendDarkState(self.ID,self.currentInstruction.theDarkState.value)

        if(self.isInstructionUpdateNeeded):
            self.theOptoLid.UpdateWithInstruction(self.currentInstruction)
            self.isInstructionUpdateNeeded=False

        self.theOptoLid.SetOptoState(lsp.analogValues)
        if(lsp.optoState1!=self.theOptoLid.optoStateCol1 or lsp.optoState2!=self.theOptoLid.optoStateCol2):
            self.MP.SendOptoState(self.ID,self.theOptoLid.optoStateCol1,self.theOptoLid.optoStateCol2)

    def ReadFirmwareVersion(self):
        # The version decides the instruction packet format. Returns False if the request timed out.
        v = self.MP.GetVersion(self.ID)
        if(v is None):
            return False
        self.firmwareVersion = v.decode("utf-8", errors="replace")
        # No answer means 1.0.5, and that board has just logged the request as an unknown command.
        self.maskProbeError = (v == COMM.LEGACY_VERSION)
        if(UsesV2Instructions(self.firmwareVersion)):
            self.DFMSubType = Enums.DFMSUBTYPE.V2
        else:
            self.DFMSubType = Enums.DFMSUBTYPE.V1_0_5
        # The meaning of the error bits also depends on the firmware.
        self.currentDFMErrors.display = DFMErrors.V3ErrorDisplay(self.firmwareVersion)
        self.isVersionGetNeeded = False
        return True

    def HasPendingCommands(self):
        """True while the DFM has a buffer reset, instruction or linkage waiting to be sent."""
        return self.isBufferResetNeeded or self.isInstructionUpdateNeeded or self.isLinkageSetNeeded

    def CheckStatusV3(self):
        # A DFM that isn't answering, or isn't being read, isn't sent anything: the commands would
        # only time out. Any other status, errors included, still gets its commands, so a bad read
        # doesn't hold back a new Interval.
        if self.status == Enums.CURRENTSTATUS.MISSING or self.status == Enums.CURRENTSTATUS.UNDEFINED:
            if(self.status == Enums.CURRENTSTATUS.MISSING):
                for name in self._PendingCommandNames():
                    self._CommandWaiting(name)
            return
        self.SendCommands()

    def SendCommands(self):
        """Sends whatever the DFM is waiting for: its version first, then a buffer reset, its
        instruction and its linkage. Commands that aren't acknowledged are retried, but not on
        every pass."""
        if(time.monotonic() < self.retryTime):
            return
        isFailed = False
        # Get the version first so the first instruction is sent in the right format.
        if(self.isVersionGetNeeded):
            if self.ReadFirmwareVersion():
                self._CommandSucceeded("version request")
            else:
                self._CommandFailed("version request")
                isFailed = True
        # Each flag is cleared before sending so that a new request made while the command is
        # in flight (e.g. an instruction change from the GUI thread) is not lost.
        if(self.isBufferResetNeeded):
            self.isBufferResetNeeded=False
            # The indexes start again when the first read after the reset arrives (ProcessPackets).
            if self.MP.SendBufferReset(self.ID):
                self._CommandSucceeded("buffer reset")
            else:
                self.isBufferResetNeeded=True
                print("Buffer reset NACKed")
                self._CommandFailed("buffer reset")
                isFailed = True
        if(self.isInstructionUpdateNeeded and not self.isVersionGetNeeded):
            self.isInstructionUpdateNeeded=False
            paradigm = self.currentInstruction.paradigm
            number = self.instructionNumber
            if(COMM.UsesParadigmFirmware(self.firmwareVersion)):
                # The Wells keep their Paradigm state while the Paradigm stays the same.
                keepState = paradigm.name == self.lastSentParadigmName
                isSent = self.MP.SendParadigmInstruction(self.ID, self.currentInstruction, number, keepState)
                if isSent:
                    # Records show the number of the instruction the DFM runs (_CheckRunningInstruction).
                    if(number != self.ackedInstructionNumber):
                        self.instructionResends = 0
                    self.ackedInstructionNumber = number
                    self.ackedInstructionTime = time.monotonic()
            else:
                # Older firmware misreads what it doesn't know and runs a different rule. The Program
                # check refuses that before a start; this catches a board swapped since then. Nothing
                # is sent, so the DFM keeps its last instruction.
                reason = paradigm.FirmwareNeeded(COMM.FirmwareVersionTuple(self.firmwareVersion))
                if(reason is not None):
                    self.NewMessage(self.ID,datetime.datetime.today(),0,"DFM {} (firmware {}) can't run this Interval: {}".format(self.ID,self.firmwareVersion,reason),Enums.MESSAGETYPE.ERROR)
                    isSent = True   # nothing to retry
                elif(self.DFMSubType == Enums.DFMSUBTYPE.V2):
                    isSent = self.MP.SendInstructionDFMV2_0(self.ID, self.currentInstruction)
                else:
                    isSent = self.MP.SendInstructionDFMV1_0_5(self.ID, self.currentInstruction)
            if isSent:
                self.lastSentParadigmName = paradigm.name
                self._CommandSucceeded("instruction")
            else:
                self.isInstructionUpdateNeeded=True
                print("Instruction update NACKed")
                self._CommandFailed("instruction")
                # The firmware NACKs an instruction in the wrong format, so check the version again.
                self.isVersionGetNeeded = True
                isFailed = True
        if(self.isLinkageSetNeeded):
            self.isLinkageSetNeeded=False
            if self.MP.SendLinkage(self.ID,self.currentLinkage):
                self._CommandSucceeded("linkage")
            else:
                self.isLinkageSetNeeded=True
                print("Linkage update NACKed")
                self._CommandFailed("linkage")
                isFailed = True
        if(isFailed):
            self.retryTime = time.monotonic() + COMMAND_RETRY_INTERVAL

    def _PendingCommandNames(self):
        names = []
        if(self.isBufferResetNeeded):
            names.append("buffer reset")
        if(self.isInstructionUpdateNeeded):
            names.append("instruction")
        if(self.isLinkageSetNeeded):
            names.append("linkage")
        return names

    def _CommandDescription(self,name):
        if(name != "instruction"):
            return name
        index, cycle = self.currentPosition
        if(index is None):
            return "instruction ({})".format("all LEDs on" if self.isOutputsOn else "all LEDs off")
        return "instruction for Interval {}, Cycle {}".format(index+1, cycle)

    def _CommandFailed(self,name):
        """A command wasn't acknowledged. After 3 failures in a row, or 10 s, it is an error."""
        trouble = self.commandTrouble.setdefault(name, [time.monotonic(), 0, False])
        trouble[1] += 1
        seconds = time.monotonic() - trouble[0]
        if(not trouble[2] and (trouble[1] >= COMMAND_FAILURES_REPORTED or seconds >= COMMAND_WAIT_REPORTED)):
            trouble[2] = True
            self.NewMessage(self.ID,datetime.datetime.today(),0,
                            "DFM {} hasn't acknowledged its {} ({} tries over {:.0f} s). Still trying.".format(
                                self.ID,self._CommandDescription(name),trouble[1],seconds),Enums.MESSAGETYPE.ERROR)

    def _CommandWaiting(self,name):
        """A command isn't being tried because the DFM isn't answering. After 10 s it is an error."""
        trouble = self.commandTrouble.setdefault(name, [time.monotonic(), 0, False])
        seconds = time.monotonic() - trouble[0]
        if(not trouble[2] and seconds >= COMMAND_WAIT_REPORTED):
            trouble[2] = True
            self.NewMessage(self.ID,datetime.datetime.today(),0,
                            "DFM {} isn't answering, so its {} hasn't been sent for {:.0f} s. Still trying.".format(
                                self.ID,self._CommandDescription(name),seconds),Enums.MESSAGETYPE.ERROR)

    def _CommandSucceeded(self,name):
        trouble = self.commandTrouble.pop(name, None)
        if(trouble is not None and trouble[2]):
            self.NewMessage(self.ID,datetime.datetime.today(),0,
                            "DFM {} acknowledged its {} after {:.0f} s.".format(
                                self.ID,self._CommandDescription(name),time.monotonic()-trouble[0]),Enums.MESSAGETYPE.NOTICE)

    def _CheckRunningInstruction(self,packets):
        """Firmware 4.0.0 repeats the number of the instruction it runs in every record. The newest
        record (in a reply that wasn't full) of a read made after the last instruction was
        acknowledged must show that number. If it doesn't, the DFM lost the instruction or never
        applied it, so it is sent again."""
        last = packets[-1]
        if(self.ackedInstructionNumber is None or self.isInstructionUpdateNeeded or self.restartPackets is not None
                or last.processResult != Enums.PROCESSEDPACKETRESULT.OKAY or not last.isV4 or last.isFullReply
                or last.readTime is None or last.readTime < self.ackedInstructionTime + INSTRUCTION_APPLY_SECONDS):
            return
        if(last.instructionNumber == self.ackedInstructionNumber):
            self.instructionResends = 0
            return
        info = self.instructionInfo.get(self.ackedInstructionNumber)
        where = "outside the Program" if info is None or info.index is None else "Interval {}, Cycle {}".format(info.index+1, info.cycle)
        if(self.instructionResends >= MAX_INSTRUCTION_RESENDS):
            if(self.instructionResends == MAX_INSTRUCTION_RESENDS):
                self.instructionResends += 1
                self.NewMessage(self.ID,datetime.datetime.today(),last.recordIndex,
                                "DFM {} still runs instruction {} instead of {} ({}) after it was sent {} more times. Not sending it again.".format(
                                    self.ID,last.instructionNumber,self.ackedInstructionNumber,where,MAX_INSTRUCTION_RESENDS),
                                Enums.MESSAGETYPE.ERROR)
            return
        self.instructionResends += 1
        self.NewMessage(self.ID,datetime.datetime.today(),last.recordIndex,
                        "DFM {} is running instruction {}, not {} ({}). Sending it again.".format(
                            self.ID,last.instructionNumber,self.ackedInstructionNumber,where),Enums.MESSAGETYPE.ERROR)
        self.isInstructionUpdateNeeded = True
    #endregion
