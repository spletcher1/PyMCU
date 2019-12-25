from enum import Enum
import array
import datetime
from Enums import PROCESSEDPACKETRESULT

class StatusPacket:
    def __init__(self,sampleIndex):
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
    def ProcessStatusPacket(self,bytesData,timeOfMeasure,packetNum):        
        ## This function should receive packetnumbers 0-4
        self.packetTime = timeOfMeasure - datetime.timedelta(microseconds=(5-packetNum)*200000)
        indexer = (packetNum*61)+4
        # Calculate the checksum
        calculatedCheckSum=0
        for cs in range(indexer,(indexer+57)) :
            calculatedCheckSum+=bytesData[cs]
        calculatedCheckSum = (calculatedCheckSum ^ 0xFFFFFFFF) + 0x01
        expectedCheckSum = bytesData[(indexer+57)]<<24
        expectedCheckSum += bytesData[(indexer+58)]<<16
        expectedCheckSum += bytesData[(indexer+59)]<<8
        expectedCheckSum += bytesData[(indexer+60)]
       
        if(calculatedCheckSum != expectedCheckSum):            
            return PROCESSEDPACKETRESULT.CHECKSUMERROR

        self.errorFlags = bytesData[indexer]

        for i in range(0,12):
            baseindex=(i*3)+(indexer+1)
            currentValue = bytesData[baseindex]<<16
            currentValue += bytesData[baseindex+1]<<8
            currentValue += bytesData[baseindex+2]
            self.analogValues[i] = currentValue >>7

        currentValue = bytesData[(indexer+37)]<<16
        currentValue += bytesData[(indexer+38)]<<8
        currentValue += bytesData[(indexer+39)]
        self.voltsIn = ((currentValue>>7)/(1024))*3.3*2

        self.optoState1 = bytesData[(indexer+40)]
        self.optoState2 = bytesData[(indexer+41)]

        currentValue = bytesData[(indexer+42)]<<8
        currentValue += bytesData[(indexer+43)]
        self.optoFrequency = currentValue

        currentValue = bytesData[(indexer+44)]<<8
        currentValue += bytesData[(indexer+45)]
        self.optoPulseWidth = currentValue

        self.darkStatus = bytesData[(indexer+46)]
        
        currentValue = bytesData[(indexer+47)]<<24
        currentValue += bytesData[(indexer+48)]<<16
        currentValue += bytesData[(indexer+49)]<<8
        currentValue += bytesData[(indexer+50)]
        self.temp = currentValue/1000.0

        currentValue = bytesData[(indexer+51)]<<24
        currentValue += bytesData[(indexer+52)]<<16
        currentValue += bytesData[(indexer+53)]<<8
        currentValue += bytesData[(indexer+54)]
        self.humidity = currentValue/1000.0

        currentValue = bytesData[(indexer+55)]<<8
        currentValue += bytesData[(indexer+56)]
        self.lux = currentValue

        return PROCESSEDPACKETRESULT.OKAY   
    def GetConsolePrintPacket(self):
        tmp = self.packetTime.microsecond/1000
        ss = self.packetTime.strftime("%m/%d/%Y %H:%M:%S")
        ss+=' {:7.2f}'.format(tmp)
        ss += '  Wells: {:4d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}'.format(self.analogValues[0],self.analogValues[1],self.analogValues[2],self.analogValues[3],self.analogValues[4],self.analogValues[5],self.analogValues[6],self.analogValues[7],self.analogValues[8],self.analogValues[9],self.analogValues[10],self.analogValues[11])       
        ss += '   E:{:<4d}  T:{:<6.2f}  H:{:<6.2f}  L:{:<4d}  V:{:4.2f}  OS1:{:02X}  OS2:{:02X}'.format(self.errorFlags,self.temp,self.humidity,self.lux,self.voltsIn,self.optoState1,self.optoState2)
        ss += '  D:{:<2d}  F:{:<4d}  PW:{:<4d}'.format(self.darkStatus,self.optoFrequency,self.optoPulseWidth)
        return ss 
    def GetDataBufferPrintPacket(self):
        tmp = self.packetTime.microsecond/1000
        ss = self.packetTime.strftime("%m/%d/%Y,%H:%M:%S,")
        ss+='{:.2f},{:d},'.format(tmp,self.sample)
        ss += '{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},'.format(self.analogValues[0],self.analogValues[1],self.analogValues[2],self.analogValues[3],self.analogValues[4],self.analogValues[5],self.analogValues[6],self.analogValues[7],self.analogValues[8],self.analogValues[9],self.analogValues[10],self.analogValues[11])
        ss += '{:.2f},{:0.2f},{:d},{:0.2f},'.format(self.temp,self.humidity,self.lux,self.voltsIn)
        ss += '{:d},{:d},{:d},{:d},{:d},{:d}\n'.format(self.darkStatus,self.optoFrequency,self.optoPulseWidth,self.optoState1,self.optoState2,self.errorFlags)
        return ss 

        


