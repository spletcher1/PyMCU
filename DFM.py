import array
import datetime
import time

import COMM
import DataBuffer
import DFMErrors
import Enums
import Event
import Instruction
import Message
import OptoLid

# Seconds to wait before retrying commands that a DFM did not acknowledge.
COMMAND_RETRY_INTERVAL = 1.0

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

class DFM:
    DFM_message = Event.Event()
    #region Initialization, etc.
    def __init__(self,id,dfmType,mp):
        self.MP = mp
        self.ID=id
        self.DFMType = dfmType
        ## Set this to 1.5 and only change if found to be needed.
        self.DFMSubType = Enums.DFMSUBTYPE.V1_5
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
        self.isInstructionUpdateNeeded=False
        self.isBufferResetNeeded=False
        # This is true because we need to get this ASAP for each DFM upon connection.
        self.isVersionGetNeeded = True
        self.isLinkageSetNeeded=False
        # False for firmware this PyMCU can't drive (4.0.0 and later), which is then left alone.
        self.isSupported = True
        self.retryTime=0.0
        if(self.DFMType==Enums.DFMTYPE.PLETCHERV3):
            # Narrowed down once the firmware version is known.
            self.currentDFMErrors = DFMErrors.DFMErrors(DFMErrors.V3_ERROR_DISPLAY_BEFORE_2_0_2)
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
            # Values over 40000 carry the firmware's +65536 'in training' flag.
            value = tmp.analogValues[i]-self.signalBaselines[i]
            if(tmp.analogValues[i]>40000):
                value -= 65536
            resultArray[i]=max(value,0)
        return resultArray

    def SetIdleStatus(self):
        ## Idle is opto off, dark running as its has been, and default other parameters.
        self.currentInstruction = Instruction.DFMInstruction()
        self.isInstructionUpdateNeeded=True

    def SetOutputsOn(self):
        self.currentInstruction = Instruction.DFMInstruction()
        self.currentInstruction.SetOptoValues([0]*12)
        self.isInstructionUpdateNeeded=True

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

        for sp in currentStatusPackets:
            if(sp.processResult != Enums.PROCESSEDPACKETRESULT.OKAY):
                continue
            errorFlags = sp.errorFlags
            if not isRecording:
                # Packets aren't kept then, so an overflow loses nothing. It is also certain
                # when the MCU asks for the latest packet only, as nothing drains the buffer.
                errorFlags &= ~DFMErrors.OVERFLOW_MASK
            self.currentDFMErrors.UpdateErrors(errorFlags)
            if(errorFlags!=0):
                s="DFM code: {:02X}".format(errorFlags)
                self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,s,Enums.MESSAGETYPE.NOTICE)

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
        newPackets=[]
        for sp in currentStatusPackets:
            if(sp.processResult != Enums.PROCESSEDPACKETRESULT.OKAY):
                if(sp.processResult in READ_FAILURES):
                    text, newStatus = READ_FAILURES[sp.processResult]
                    self.SetStatus(newStatus)
                    self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,"({:d}) ".format(self.ID)+text,theMessageType)
            elif(sp.recordIndex<=0):
                # It's okay now to receive these because of the fast buffer reset and call. I will not call this an error.
                print("({:d}) Empty packet received".format(self.ID))
            elif(sp.recordIndex<=self.lastDFMIndex):
                ## If there are readings sent multiple times, don't add them to the data file, but let us know they occured.
                s="({:d}) Repeated index: ({:d}) ".format(sp.recordIndex,self.lastDFMIndex)
                self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,s,Enums.MESSAGETYPE.ERROR)
            else:
                self._AddPacket(sp,saveDataToQueue)
                newPackets.append(sp)

        # Only packets seen for the first time are reported, so each packet's error flags count
        # once. Resent packets were counted when they first came, and with partial ACKs the good
        # packets before a bad one aren't sent again.
        if(newPackets):
            self.UpdateReportedValues(newPackets,saveDataToQueue)
        self.CheckStatus()

    def _AddPacket(self,sp,saveDataToQueue):
        sp.sample = self.sampleIndex
        if(self.theData.NewData(sp,saveDataToQueue)==False):
            s="({:d}) Data queue full".format(self.ID)
            self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,s,Enums.MESSAGETYPE.ERROR)
            self.SetStatus(Enums.CURRENTSTATUS.ERROR)
        elif(saveDataToQueue):
            if(self.DFMType==Enums.DFMTYPE.PLETCHERV3):
                if(sp.recordIndex != (self.lastDFMIndex+1)):
                    s="({:d}) Skipped index: ({:d}) ".format(sp.recordIndex,self.lastDFMIndex)
                    self.NewMessage(self.ID,sp.packetTime,sp.recordIndex,s,Enums.MESSAGETYPE.ERROR)
                    self.SetStatus(Enums.CURRENTSTATUS.ERROR)
                self.lastDFMIndex = sp.recordIndex
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
    def UpdateInstruction(self,instruct,useBaseline):
        # There is no instruction before a program starts or for Constant programs; keep the current one.
        if(instruct is None or instruct is self.currentInstruction):
            return
        self.currentInstruction = instruct
        if(useBaseline):
            self.currentInstruction.SetBaseline(self.signalBaselines)
        self.isInstructionUpdateNeeded=True

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
        if(COMM.UsesParadigmFirmware(self.firmwareVersion)):
            # Said once. The board stays on the DFM page with its firmware, and nothing is sent to it.
            if(self.isSupported):
                self.isSupported = False
                self.NewMessage(self.ID,datetime.datetime.today(),0,"DFM {} runs firmware {}, which needs PyMCU 4.0.0 or later".format(self.ID,self.firmwareVersion),Enums.MESSAGETYPE.ERROR)
        else:
            self.isSupported = True
        if(UsesV2Instructions(self.firmwareVersion)):
            self.DFMSubType = Enums.DFMSUBTYPE.V2
        else:
            self.DFMSubType = Enums.DFMSUBTYPE.V1_5
        # The meaning of the error bits also depends on the firmware.
        self.currentDFMErrors.display = DFMErrors.V3ErrorDisplay(self.firmwareVersion)
        self.isVersionGetNeeded = False
        return True

    def CheckStatusV3(self):
        # To avoid sending repeated instructions to missing DFM that are never acked and therefore continue to be queued and sent.
        if self.status == Enums.CURRENTSTATUS.MISSING or self.status == Enums.CURRENTSTATUS.ERROR or self.status == Enums.CURRENTSTATUS.UNDEFINED:
            return
        # A board on firmware this PyMCU can't drive would NACK every instruction. It has been reported.
        if not self.isSupported:
            return
        # Commands that were not acknowledged are retried, but not on every pass.
        if(time.monotonic() < self.retryTime):
            return
        isFailed = False
        # Get the version first so the first instruction is sent in the right format.
        if(self.isVersionGetNeeded):
            if not self.ReadFirmwareVersion():
                isFailed = True
        # Each flag is cleared before sending so that a new request made while the command is
        # in flight (e.g. an instruction change from the GUI thread) is not lost.
        if(self.isBufferResetNeeded):
            self.isBufferResetNeeded=False
            # The indexes start again when the first read after the reset arrives (ProcessPackets).
            if not self.MP.SendBufferReset(self.ID):
                self.isBufferResetNeeded=True
                print("Buffer reset NACKed")
                isFailed = True
        if(self.isInstructionUpdateNeeded and not self.isVersionGetNeeded):
            self.isInstructionUpdateNeeded=False
            # Firmware 1.0.5 misreads settings it doesn't know and runs a different rule. The Program
            # check refuses those before a start; this catches a board swapped since then. Nothing is
            # sent, so the DFM keeps its last instruction.
            reason = None if self.DFMSubType == Enums.DFMSUBTYPE.V2 else self.currentInstruction.FirmwareNeeded()
            if(reason is not None):
                self.NewMessage(self.ID,datetime.datetime.today(),0,"DFM {} (firmware {}) can't run this Interval: {}".format(self.ID,self.firmwareVersion,reason),Enums.MESSAGETYPE.ERROR)
                isSent = True   # nothing to retry
            elif(self.DFMSubType == Enums.DFMSUBTYPE.V2):
                isSent = self.MP.SendInstructionDFMV2_0(self.ID, self.currentInstruction)
            else:
                isSent = self.MP.SendInstructionDFMV1_5(self.ID, self.currentInstruction)
            if not isSent:
                self.isInstructionUpdateNeeded=True
                print("Instruction update NACKed")
                # The firmware NACKs an instruction in the wrong format, so check the version again.
                self.isVersionGetNeeded = True
                isFailed = True
        if(self.isLinkageSetNeeded):
            self.isLinkageSetNeeded=False
            if not self.MP.SendLinkage(self.ID,self.currentLinkage):
                self.isLinkageSetNeeded=True
                print("Linkage update NACKed")
                isFailed = True
        if(isFailed):
            self.retryTime = time.monotonic() + COMMAND_RETRY_INTERVAL
    #endregion
