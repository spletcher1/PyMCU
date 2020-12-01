import array
import datetime
from Enums import PROCESSEDPACKETRESULT,DFMTYPE

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

    def ProcessStatusPacket(self,bytesData,startTime,index=0):     
        if(self.DFMType==DFMTYPE.SABLEV2):           
            self.ProcessStatusPacketSableV2(bytesData,startTime)
        elif(self.DFMType==DFMTYPE.PLETCHERV2):            
            return self.ProcessStatusPacketPletcherV2(bytesData,startTime)
        elif(self.DFMType==DFMTYPE.PLETCHERV3):            
            return self.ProcessStatusPacketPletcherV3(bytesData,startTime,index)

    def AddEnvironmentalInformation(self,temp,lux,humid):
        self.temp = int(temp)
        self.humidity = int(humid)       
        self.lux = int(lux)

    def ProcessStatusPacketSableV2(self,bytesData,currentTime):        
        if(len(bytesData)!=52):
            self.processResult = PROCESSEDPACKETRESULT.WRONGNUMBYTES   
            return 
        
        wellIndexer=[0,2,1,3,10,7,11,4,8,5,9,6]   
        self.errorFlags = 0        
        calculatedCheckSum=0

        for i in range(0,12):
            baseindex=(i*4)
            currentValue = bytesData[baseindex]
            currentValue += bytesData[baseindex+1]<<8
            currentValue += bytesData[baseindex+2]<<16
            currentValue += bytesData[baseindex+3]<<24
            calculatedCheckSum+=currentValue
            self.analogValues[wellIndexer[i]] = currentValue >> 7
           
        self.voltsIn = 0
        self.optoState1 = 0
        self.optoState2 = 0        

        self.optoFrequency = 0
        self.optoPulseWidth = 0
        self.darkStatus = 0        

        self.temp = 0
        self.humidity = 0       
        self.lux = 0
        self.recordIndex = 1        
        self.packetTime = currentTime

        expectedCheckSum = bytesData[48]
        expectedCheckSum += bytesData[49]<<8
        expectedCheckSum += bytesData[50]<<16
        expectedCheckSum += bytesData[51]<<24
       
        if(calculatedCheckSum != expectedCheckSum):            
            print("Checksum error")
            self.processResult = PROCESSEDPACKETRESULT.CHECKSUMERROR
            return

        self.processResult = PROCESSEDPACKETRESULT.OKAY   
        return

    def ProcessStatusPacketPletcherV2(self,bytesData,currentTime):           
        if(len(bytesData)!=64):
            self.processResult = PROCESSEDPACKETRESULT.WRONGNUMBYTES   
            return

        wellIndexer=[0,2,1,3,10,7,11,4,8,5,9,6]           
        self.errorFlags = 0        
        calculatedCheckSum=0

        for i in range(0,12):
            baseindex=(i*4)
            currentValue = bytesData[baseindex]
            currentValue += bytesData[baseindex+1]<<8
            currentValue += bytesData[baseindex+2]<<16
            currentValue += bytesData[baseindex+3]<<24
            calculatedCheckSum+=currentValue
            self.analogValues[wellIndexer[i]] = currentValue >> 7
           
        self.voltsIn = 0

        currentValue = bytesData[52]
        currentValue += bytesData[53]<<8
        currentValue += bytesData[54]<<16
        currentValue += bytesData[55]<<24
        self.optoState1 = currentValue
        calculatedCheckSum +=currentValue

        currentValue = bytesData[56]
        currentValue += bytesData[57]<<8
        currentValue += bytesData[58]<<16
        currentValue += bytesData[59]<<24
        self.optoState2 = currentValue
        calculatedCheckSum +=currentValue

        self.optoFrequency = bytesData[49]
        self.optoPulseWidth = bytesData[50]
        self.darkStatus = bytesData[48]
        
        calculatedCheckSum += bytesData[48]+(bytesData[49]<<8)+(bytesData[50]<<16)

        self.temp = 0
        self.humidity = 0       
        self.lux = 0             
        self.recordIndex = 1    
        self.packetTime = currentTime

        expectedCheckSum = bytesData[60]
        expectedCheckSum += bytesData[61]<<8
        expectedCheckSum += bytesData[62]<<16
        expectedCheckSum += bytesData[63]<<24
       
        #calculatedCheckSum = 637322
        if(calculatedCheckSum != expectedCheckSum):   
            print("Checksum error: "+str(expectedCheckSum)+"  "+str(calculatedCheckSum))                            
            self.processResult = PROCESSEDPACKETRESULT.CHECKSUMERROR    
            return    

        self.processResult = PROCESSEDPACKETRESULT.OKAY   
        return

    def ProcessStatusPacketPletcherV3(self,bytesData,startTime,packetNum):        
        ## This function should receive packetnumbers 0-4        
        indexer = (packetNum*56)
        # Calculate the checksum
        calculatedCheckSum=0        
        for cs in range(indexer,(indexer+52)) :
            calculatedCheckSum+=bytesData[cs]
        calculatedCheckSum = (calculatedCheckSum ^ 0xFFFFFFFF) + 0x01
        expectedCheckSum = bytesData[(indexer+52)]<<24
        expectedCheckSum += bytesData[(indexer+53)]<<16
        expectedCheckSum += bytesData[(indexer+54)]<<8
        expectedCheckSum += bytesData[(indexer+55)]
       
        #if(calculatedCheckSum != expectedCheckSum):     
        #    print(str(calculatedCheckSum)+":"+str(expectedCheckSum))       
        #    self.processResult =  PROCESSEDPACKETRESULT.CHECKSUMERROR
        #    return
        
        ## Add one to move past the ID
        indexer+=1
       
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

        self.optoState1 = bytesData[(indexer+40)] <<8
        self.optoState1 += bytesData[(indexer+41)]
        #self.optoState2 = bytesData[(indexer+41)]
        self.optoState2 =0
        
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
        self.recordIndex = currentValue        
        self.packetTime = startTime + datetime.timedelta(seconds=currentValue*0.2)        
        #self.packetTime = datetime.datetime.today()

        if(calculatedCheckSum != expectedCheckSum):     
            print(str(calculatedCheckSum)+":"+str(expectedCheckSum))       
            self.processResult =  PROCESSEDPACKETRESULT.CHECKSUMERROR
            return

        self.processResult =  PROCESSEDPACKETRESULT.OKAY      
        return

    def GetConsolePrintPacket(self):
        tmp = self.packetTime.microsecond/1000
        ss = "("+str(self.DFMID)+":"+str(self.sample)+") "
        ss += self.packetTime.strftime("%m/%d/%Y %H:%M:%S")
        ss+=' {:7.2f}'.format(tmp)
        ss += '  Wells: {:4d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}{:6d}'.format(self.analogValues[0],self.analogValues[1],self.analogValues[2],self.analogValues[3],self.analogValues[4],self.analogValues[5],self.analogValues[6],self.analogValues[7],self.analogValues[8],self.analogValues[9],self.analogValues[10],self.analogValues[11])       
        ss += '   E:{:<4d}  T:{:<6.2f}  H:{:<6.2f}  L:{:<4d}  V:{:4.2f}  OS1:{:02X}  OS2:{:02X}'.format(self.errorFlags,self.temp,self.humidity,self.lux,self.voltsIn,self.optoState1,self.optoState2)
        ss += '  D:{:<2d}  F:{:<4d}  PW:{:<4d} Ind:{:<6d}'.format(self.darkStatus,self.optoFrequency,self.optoPulseWidth,self.recordIndex)
        return ss 
    def GetDataBufferPrintPacket(self):
        tmp = self.packetTime.microsecond/1000
        ss = self.packetTime.strftime("%m/%d/%Y,%H:%M:%S,")
        ss+='{:.2f},{:d},'.format(tmp,self.sample)
        ss += '{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},{:d},'.format(self.analogValues[0],self.analogValues[1],self.analogValues[2],self.analogValues[3],self.analogValues[4],self.analogValues[5],self.analogValues[6],self.analogValues[7],self.analogValues[8],self.analogValues[9],self.analogValues[10],self.analogValues[11])
        ss += '{:.2f},{:0.2f},{:d},{:0.2f},'.format(self.temp,self.humidity,self.lux,self.voltsIn)
        ss += '{:d},{:d},{:d},{:d},{:d},{:d},{:d}\n'.format(self.darkStatus,self.optoFrequency,self.optoPulseWidth,self.optoState1,self.optoState2,self.errorFlags,self.recordIndex)
        return ss 
