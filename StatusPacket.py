import array
import datetime
from Enums import PROCESSEDPACKETRESULT,DFMTYPE

V3_PACKET_SIZE = 56
# DFM firmware 4.0.0 and later: the Status record with Paradigm state.
V4_PACKET_SIZE = 127
# A V3 status packet is filled in every 200 ms, so its index gives its time.
V3_PACKET_INTERVAL = 0.2
# Order of the wells in V2 (I2C) packets.
V2_WELL_ORDER = [0,2,1,3,10,7,11,4,8,5,9,6]
# Paradigm types whose Requirement and Progress mean something (Paradigm.ParadigmType).
RATIO_TYPES = (4, 5)

DATA_COLUMNS = ("Date,Time,MSec,Sample,W1,W2,W3,W4,W5,W6,W7,W8,W9,W10,W11,W12,Temp,Humid,LUX,VoltsIn,"
                "Dark,OptoFreq,OptoPW,OptoCol1,OptoCol2,Error,Index")
# Added after DATA_COLUMNS in DFM data files. Phase is A (Acclimation) or M (Main).
PARADIGM_COLUMNS = "Interval,Cycle,Paradigm," + ",".join(
    "{}{}".format(name, w) for name in ("Phase", "Activations", "Requirement", "Progress", "OnMs") for w in range(1, 13))
# Written where a value doesn't apply; pandas and R read it as missing.
MISSING = "NA"
_MISSING_PARADIGM_COLUMNS = ",".join([MISSING] * len(PARADIGM_COLUMNS.split(",")))


def Checksum32(data):
    """Two's complement of the byte sum, as computed by the V3 firmware."""
    return -sum(data) & 0xFFFFFFFF


def _BigEndian(data, start, size):
    return int.from_bytes(bytes(data[start:start+size]), "big")


def _LittleEndian(data, start, size):
    return int.from_bytes(bytes(data[start:start+size]), "little")


class StatusPacket:
    def __init__(self,sampleIndex,DFMID,DFMType):
        self.analogValues=array.array("i",(0 for i in range(0,12)))
        self.packetTime = datetime.datetime.today()
        self.voltsIn = 0.0
        self.temp = 0.0
        self.humidity = 0.0
        self.lux=0
        self.sample=sampleIndex
        self.optoState1=0
        self.optoState2=0
        self.darkStatus=0
        self.optoFrequency=0
        self.optoPulseWidth=0
        self.errorFlags=0
        self.recordIndex=1
        self.DFMID=DFMID
        self.processResult=''
        self.DFMType=DFMType
        # How many times the reader had reset this DFM's buffer when the packet was read. Record
        # indexes start again at 1 after each reset.
        self.bufferResetCount=0
        # Whether the read that brought this packet was a full reply (more were waiting on the
        # DFM), and how long after the DFM's last buffer reset that read was made, in seconds.
        self.isFullReply=False
        self.secondsSinceReset=None
        # When that read was made (time.monotonic(), the same clock in every process).
        self.readTime=None
        # Paradigm state, from firmware 4.0.0 records. DFM.ProcessPackets fills in the Interval,
        # Cycle, Paradigm name and the Activation totals (carried past 65535).
        self.isV4 = False
        self.instructionNumber = 0
        self.paradigmType = None
        self.phases = None
        self.onMs = None
        self.activationsRaw = None
        self.activationTotals = None
        self.requirement = None
        self.progress = None
        self.interval = None
        self.cycle = None
        self.paradigmName = ""
        # True for a 4.0.0 record from before the first Program Interval of the recording.
        self.isBeforeProgram = False

    def ProcessStatusPacket(self,bytesData,startTime,index=0,recordSize=V3_PACKET_SIZE):
        if(self.DFMType==DFMTYPE.SABLEV2):
            self.ProcessStatusPacketSableV2(bytesData,startTime)
        elif(self.DFMType==DFMTYPE.PLETCHERV2):
            self.ProcessStatusPacketPletcherV2(bytesData,startTime)
        elif(self.DFMType==DFMTYPE.PLETCHERV3):
            if(recordSize==V4_PACKET_SIZE):
                self.ProcessStatusPacketPletcherV4(bytesData,startTime,index)
            else:
                self.ProcessStatusPacketPletcherV3(bytesData,startTime,index)
        elif(self.DFMType==DFMTYPE.ENVMONV3):
            self.ProcessStatusPacketEnvMonV3(bytesData,startTime,index)

    def AddEnvironmentalInformation(self,temp,lux,humid):
        self.temp = temp
        self.humidity = humid
        self.lux = lux

    #region V2 (I2C) packets: little-endian 32-bit well values, then an additive checksum
    def _ProcessV2Wells(self,bytesData):
        checksum=0
        for i in range(0,12):
            value = _LittleEndian(bytesData,i*4,4)
            checksum+=value
            self.analogValues[V2_WELL_ORDER[i]] = value >> 7
        return checksum

    def _FinishV2Packet(self,bytesData,currentTime,checksumIndex,calculatedCheckSum):
        self.temp = 0
        self.humidity = 0
        self.lux = 0
        self.recordIndex = 1
        self.packetTime = currentTime
        expectedCheckSum = _LittleEndian(bytesData,checksumIndex,4)
        if(calculatedCheckSum != expectedCheckSum):
            print("Checksum error: "+str(expectedCheckSum)+"  "+str(calculatedCheckSum))
            self.processResult = PROCESSEDPACKETRESULT.CHECKSUMERROR
        else:
            self.processResult = PROCESSEDPACKETRESULT.OKAY

    def ProcessStatusPacketSableV2(self,bytesData,currentTime):
        if(len(bytesData)!=52):
            self.processResult = PROCESSEDPACKETRESULT.WRONGNUMBYTES
            return
        self.errorFlags = 0
        calculatedCheckSum = self._ProcessV2Wells(bytesData)
        self.voltsIn = 0
        self.optoState1 = 0
        self.optoState2 = 0
        self.optoFrequency = 0
        self.optoPulseWidth = 0
        self.darkStatus = 0
        self._FinishV2Packet(bytesData,currentTime,48,calculatedCheckSum)

    def ProcessStatusPacketPletcherV2(self,bytesData,currentTime):
        if(len(bytesData)!=64):
            self.processResult = PROCESSEDPACKETRESULT.WRONGNUMBYTES
            return
        self.errorFlags = 0
        calculatedCheckSum = self._ProcessV2Wells(bytesData)
        self.voltsIn = 0
        self.optoState1 = _LittleEndian(bytesData,52,4)
        self.optoState2 = _LittleEndian(bytesData,56,4)
        self.darkStatus = bytesData[48]
        self.optoFrequency = bytesData[49]
        self.optoPulseWidth = bytesData[50]
        calculatedCheckSum += self.optoState1 + self.optoState2 + _LittleEndian(bytesData,48,3)
        self._FinishV2Packet(bytesData,currentTime,60,calculatedCheckSum)
    #endregion

    #region V3 (UART) packets before firmware 4.0.0
    # 0 ID, 1 error flags, 2-37 wells (3 bytes each), 38-40 volts in, 41-42 opto state,
    # 43-44 opto frequency, 45-46 opto pulse width, 47 dark, 48-51 index, 52-55 checksum
    def _ProcessV3Common(self,bytesData,startTime,packetNum):
        """Sets the fields shared by DFM and EnvMon packets. Returns the packet's offset."""
        base = packetNum*V3_PACKET_SIZE
        self.errorFlags = bytesData[base+1]
        self.darkStatus = bytesData[base+47]
        self.recordIndex = _BigEndian(bytesData,base+48,4)
        self.packetTime = startTime + datetime.timedelta(seconds=self.recordIndex*V3_PACKET_INTERVAL)
        return base

    def _CheckChecksum(self,bytesData,base,size):
        calculatedCheckSum = Checksum32(bytesData[base:base+size-4])
        expectedCheckSum = _BigEndian(bytesData,base+size-4,4)
        if(calculatedCheckSum != expectedCheckSum):
            print(str(calculatedCheckSum)+":"+str(expectedCheckSum))
            self.processResult = PROCESSEDPACKETRESULT.CHECKSUMERROR
        else:
            self.processResult = PROCESSEDPACKETRESULT.OKAY

    def ProcessStatusPacketPletcherV3(self,bytesData,startTime,packetNum):
        base = self._ProcessV3Common(bytesData,startTime,packetNum)
        for i in range(0,12):
            # Each well is the sum of the last 128 readings. Old firmware sets the top bit while a
            # well is in event-based training; it is dropped (& 0xFFFF).
            self.analogValues[i] = (_BigEndian(bytesData,base+2+i*3,3) >> 7) & 0xFFFF
        self.voltsIn = ((_BigEndian(bytesData,base+38,3)>>7)/(1024))*3.3*2
        self.optoState1 = _BigEndian(bytesData,base+41,2)
        self.optoState2 = 0
        self.optoFrequency = _BigEndian(bytesData,base+43,2)
        self.optoPulseWidth = _BigEndian(bytesData,base+45,2)
        self.temp = 0
        self.humidity = 0
        self.lux = 0
        self._CheckChecksum(bytesData,base,V3_PACKET_SIZE)

    def ProcessStatusPacketEnvMonV3(self,bytesData,startTime,packetNum):
        base = self._ProcessV3Common(bytesData,startTime,packetNum)
        self.temp = _BigEndian(bytesData,base+2,4)/1000.0
        self.humidity = _BigEndian(bytesData,base+6,4)/1000.0
        self.lux = _BigEndian(bytesData,base+10,4)/1000.0
        # Bytes 14-19 are on/off states, shown as wells 1-6.
        for i in range(0,12):
            self.analogValues[i] = 500 if i<6 and bytesData[base+14+i]!=0 else 0
        self.voltsIn = 0.0
        self._CheckChecksum(bytesData,base,V3_PACKET_SIZE)
    #endregion

    #region V4 packets (firmware 4.0.0 and later): struct StatusPacket in DFMV3_V2/src/PacketManager.h
    # 0 ID, 1 error flags, 2-3 instruction number, 4 Paradigm type, 5-6 Phase bits, 7-30 wells,
    # 31-32 volts in, 33-34 LED state, 35-46 LED on ms, 47-70 Activations, 71-94 Requirement,
    # 95-118 Progress, 119-122 index, 123-126 checksum. Wells and volts are averages.
    def ProcessStatusPacketPletcherV4(self,bytesData,startTime,packetNum):
        base = packetNum*V4_PACKET_SIZE
        self.isV4 = True
        self.errorFlags = bytesData[base+1]
        self.instructionNumber = _BigEndian(bytesData,base+2,2)
        self.paradigmType = bytesData[base+4]
        phaseBits = _BigEndian(bytesData,base+5,2)
        self.phases = [(phaseBits >> w) & 1 for w in range(0,12)]
        for i in range(0,12):
            self.analogValues[i] = _BigEndian(bytesData,base+7+i*2,2)
        self.voltsIn = (_BigEndian(bytesData,base+31,2)/1024)*3.3*2
        self.optoState1 = _BigEndian(bytesData,base+33,2)
        self.optoState2 = 0
        self.onMs = [bytesData[base+35+w] for w in range(0,12)]
        self.activationsRaw = [_BigEndian(bytesData,base+47+w*2,2) for w in range(0,12)]
        self.requirement = [_BigEndian(bytesData,base+71+w*2,2) for w in range(0,12)]
        self.progress = [_BigEndian(bytesData,base+95+w*2,2) for w in range(0,12)]
        self.recordIndex = _BigEndian(bytesData,base+119,4)
        self.packetTime = startTime + datetime.timedelta(seconds=self.recordIndex*V3_PACKET_INTERVAL)
        self.temp = 0
        self.humidity = 0
        self.lux = 0
        self._CheckChecksum(bytesData,base,V4_PACKET_SIZE)
    #endregion

    def GetConsolePrintPacket(self):
        tmp = self.packetTime.microsecond/1000
        ss = "("+str(self.DFMID)+":"+str(self.sample)+") "
        ss += self.packetTime.strftime("%m/%d/%Y %H:%M:%S")
        ss+=' {:7.2f}'.format(tmp)
        ss += '  Wells: {:4d}'.format(self.analogValues[0]) + ''.join('{:6d}'.format(v) for v in self.analogValues[1:])
        ss += '   E:{:<4d}  T:{:<6.2f}  H:{:<6.2f}  L:{:<6.2f}  V:{:4.2f}  OS1:{:02X}  OS2:{:02X}'.format(self.errorFlags,self.temp,self.humidity,self.lux,self.voltsIn,self.optoState1,self.optoState2)
        ss += '  D:{:<2d}  F:{:<4d}  PW:{:<4d} Ind:{:<6d}'.format(self.darkStatus,self.optoFrequency,self.optoPulseWidth,self.recordIndex)
        return ss

    def _ParadigmColumns(self):
        if not self.isV4:
            return _MISSING_PARADIGM_COLUMNS
        isRatio = self.paradigmType in RATIO_TYPES
        def Count(values):
            return ",".join(str(v) if isRatio and self.requirement[w] > 0 else MISSING for w, v in enumerate(values))
        totals = self.activationTotals if self.activationTotals is not None else self.activationsRaw
        # Records from before the first Program Interval (while the baseline is taken) are Interval 0.
        if self.isBeforeProgram:
            interval = "0"
        else:
            interval = MISSING if self.interval is None else str(self.interval+1)
        return ",".join([
            interval,
            MISSING if self.cycle is None else str(self.cycle),
            self.paradigmName or MISSING,
            ",".join("A" if p else "M" for p in self.phases),
            ",".join(str(v) for v in totals),
            Count(self.requirement),
            Count(self.progress),
            ",".join(str(v) for v in self.onMs)])

    def GetDataBufferPrintPacket(self):
        tmp = self.packetTime.microsecond/1000
        ss = self.packetTime.strftime("%m/%d/%Y,%H:%M:%S,")
        ss+='{:.2f},{:d},'.format(tmp,self.sample)
        ss += ''.join('{:d},'.format(v) for v in self.analogValues)
        ss += '{:.2f},{:0.2f},{:.2f},{:0.2f},'.format(self.temp,self.humidity,self.lux,self.voltsIn)
        ss += '{:d},{:d},{:d},{:d},{:d},{:d},{:d}'.format(self.darkStatus,self.optoFrequency,self.optoPulseWidth,self.optoState1,self.optoState2,self.errorFlags,self.recordIndex)
        # The Environmental Monitor's data file keeps its old columns.
        if self.DFMType != DFMTYPE.ENVMONV3:
            ss += "," + self._ParadigmColumns()
        return ss + "\n"
