import time
import _thread 
import socketserver 
from random import seed
from random import randint
import array
import StatusPacket
import platform
import serial
import Event
import Message
import datetime
import Instruction
import Enums
import Board
from cobs import cobs
import smbus2

if(platform.system()!="Windows"):
    import serial.tools.list_ports

if("MCU" in platform.node()):        
    import RPi.GPIO as GPIO

#region TESTCOMM
class TESTCOMM():
    UART_message = Event.Event()
    def __init__(self):
        self.recordIndex=1
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        TESTCOMM.UART_message.notify(tmp)   
    def _DoNothing(self):
        a=1
    def PollSlave(self,ID):
        return True
    def RequestStatus(self,ID):
        self._DoNothing()
    def SendOptoState(self, os1, os2,ID):
        self._DoNothing()
    def SendPulseWidth(self, pw,ID):
        self._DoNothing()
    def SendFrequency(self,freq,ID):
        self._DoNothing()
    def GoDark(self,ID):
        self._DoNothing()
    def ExitDark(self,ID):
        self._DoNothing()
    def SendInstruction(self,ID,anInstruction):
        return True
    def RequestBufferReset(self,ID):
        return True
    def _CreateFakeStatusPacket(self,ID):
        tmp = StatusPacket.StatusPacket(0)
        ba = bytearray(66*5)       
       
        for j in range(0,5):           
            baseindexer = (j*66)
            ba[baseindexer]=ID 
            indexer=baseindexer+1
            ba[indexer]=0x00 #Error flaj 
            for i in range(0,12):
                analog=50+randint(0,20)
                analog *=128
                ba[(3*i)+(indexer+1)]=analog >> 16
                ba[(3*i)+(indexer+2)]=(analog >> 8) & 0xFF
                ba[(3*i)+(indexer+3)]=analog & 0xFF
            
            voltsin = int((2.5/3.3)*1024*128)
            ba[(indexer+37)] = voltsin>>16
            ba[(indexer+38)] = (voltsin>>8) & 0xFF
            ba[(indexer+39)] = voltsin & 0xFF
                
            ba[(indexer+40)]=0x00 #OS1
            ba[(indexer+41)]=0x00 #OS2

            ba[(indexer+42)]=0x00 #Freq
            ba[(indexer+43)]=0x28

            ba[(indexer+44)]=0x00 #PW
            ba[(indexer+45)]=0x08

            ba[(indexer+46)]=0x00 # Dark mode

            tmp = 18 + randint(0,10) 
            tmp*=1000
            ba[(indexer+47)] = tmp>>24
            ba[(indexer+48)] = (tmp>>16) & 0xFF
            ba[(indexer+49)] = (tmp>>8) & 0xFF
            ba[(indexer+50)] = tmp & 0xFF

            tmp = 45 + randint(0,20) 
            tmp*=1000
            ba[(indexer+51)] = tmp>>24
            ba[(indexer+52)] = (tmp>>16) & 0xFF
            ba[(indexer+53)] = (tmp>>8) & 0xFF
            ba[(indexer+54)] = tmp & 0xFF

            tmp = 500 + randint(0,80) 
            ba[(indexer+55)] = (tmp>>8) & 0xFF
            ba[(indexer+56)] = tmp & 0xFF

            tmp = self.recordIndex
            ba[(indexer+57)] = tmp>>24
            ba[(indexer+58)]  = (tmp>>16) & 0xFF
            ba[(indexer+59)] = (tmp>>8) & 0xFF
            ba[(indexer+60)] = tmp & 0xFF
            
            calculatedCheckSum=0
            for cs in range(baseindexer,baseindexer+62) :
                calculatedCheckSum+=ba[cs]
            calculatedCheckSum = (calculatedCheckSum ^ 0xFFFFFFFF) + 0x01
            ba[(indexer+61)] = calculatedCheckSum>>24
            ba[(indexer+62)] = (calculatedCheckSum>>16) & 0xFF
            ba[(indexer+63)] = (calculatedCheckSum>>8) & 0xFF
            ba[(indexer+64)] = calculatedCheckSum & 0xFF

            self.recordIndex+=1
        return ba
    def GetStatusPacket(self,ID):        
        tmp = self._CreateFakeStatusPacket(ID) 
        return tmp
#endregion

class COMM():    
    COMM_message = Event.Event()    
    #region Core read/write functions
    def __init__(self):
        ## The timeout here is tricky.  For 15 packets to be sent, it seems to
        ## take about 0.150 seconds, so the timeout has to be larger than this
        ## or the packet gets cut off.
        self.thePort=serial.Serial('/dev/ttyAMA0',115200,timeout=.3)           
        self.sendPIN = 17
        GPIO.setup(self.sendPIN,GPIO.OUT)        
        GPIO.output(self.sendPIN,GPIO.LOW)
        self.i2cbus = smbus2.SMBus(1)
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        COMM.COMM_message.notify(tmp)   
    def _Write(self,s,delay=0.005):
        GPIO.output(self.sendPIN,GPIO.HIGH)       
        time.sleep(delay)    
        self.thePort.write(s.encode())               
        time.sleep(delay)     
        GPIO.output(self.sendPIN,GPIO.LOW)
    def _WriteByteArray(self,ba,delay=0.005):       
        GPIO.output(self.sendPIN,GPIO.HIGH)
        time.sleep(delay)    
        self.thePort.write(ba)   
        time.sleep(delay)             
        GPIO.output(self.sendPIN,GPIO.LOW)
    def _Read(self,numBytes):
        result=self.thePort.read(numBytes)
        return result
    def _ReadCOBSPacket(self, maxBytes):
        term = bytearray(1)
        term[0]=0x00
        result = self.thePort.read_until(term,maxBytes)
        result = result[:-1]        
        return result
    #endregion

    #region Misc Functions
    def GetAvailablePorts(self):
        ports = serial.tools.list_ports.comports()
        available_ports=[]
        for p in ports:
            available_ports.append(p.device)
        return available_ports    
    def _AddChecksumTwoBytes(self, startByte, bytes):
        checksum=0
        tmp = len(bytes)
        for i in range(startByte,tmp-2):
            checksum=checksum+bytes[i]
        checksum = (checksum ^ 0xFFFFFFFF) + 0x01
        checksum = checksum & 0x0000FFFF
        bytes[tmp-2] = (checksum>>8) & 0xFF
        bytes[tmp-1] = (checksum) & 0xFF
    def _AddChecksumFourBytes(self, startByte, ba):
        checksum=0
        tmp = len(ba)
        for i in range(startByte,tmp-4):
            checksum=checksum+ba[i]
        checksum = (checksum ^ 0xFFFFFFFF) + 0x01                      
        ba[tmp-4] = (checksum>>24) & 0xFF
        ba[tmp-3] = (checksum>>16) & 0xFF
        ba[tmp-2] = (checksum>>8) & 0xFF
        ba[tmp-1] = (checksum) & 0xFF   
    #endregion

    #region Specific DFM calls     
    def RequestStatus(self,ID):
                 
        ba = bytearray(3)
        ba[0]=ID
        ba[1]=0xFC # Indicates status request
        ba[2]=ID
        
        encodedba=cobs.encode(ba)        
        barray = bytearray(encodedba)
        barray.append(0x00)                 
        self._WriteByteArray(barray,0.001)
    
    def RequestBufferReset(self,dfm):       
        if(dfm.DFMType!=Enums.DFMTYPE.PLETCHERV3):
            return True

        self.thePort.reset_input_buffer()
        ba = bytearray(3)
        ba[0]=dfm.ID
        ba[1]=0xFE # Indicates buffer reset        
        ba[2]=dfm.ID
    
        encodedba=cobs.encode(ba)        
        barray = bytearray(encodedba)
        barray.append(0x00)            
        self._WriteByteArray(barray,0.001)
       
        tmp=self._Read(2)         
        if(len(tmp)!=2):            
            return False
        if(tmp[0]==dfm.ID):
            return True
        else:
            return False    
    def SendLinkage(self,dfm):
        if(dfm.DFMType!=Enums.DFMTYPE.PLETCHERV3):
            return True
        ba = bytearray(18)
        ba[0]=dfm.ID
        ba[1]=0xFB
        for i in range(0,12):
            ba[i+2]=dfm.currentLinkage[i]
        self._AddChecksumFourBytes(0,ba)
        encodedba=cobs.encode(ba)        
        barray = bytearray(encodedba)
        barray.append(0x00)        
        self._WriteByteArray(barray,0.006)        
        tmp=self._Read(2)
        if(len(tmp)!=2):            
            return False
        if(tmp[0]==dfm.ID):
            return True 
        else:            
            return False    

    def SendInstruction(self,ID,anInstruction):          
        ba = bytearray(41)           
        ba[0]=ID
        ba[1]=0xFD
       
        if(anInstruction.theDarkState==Enums.DARKSTATE.ON):
            ba[2]=1
        else:
            ba[2]=0
        ba[3]=(anInstruction.frequency>>8) & 0xFF
        ba[4]=(anInstruction.frequency) & 0xFF

        ba[5]=(anInstruction.pulseWidth>>8) & 0xFF
        ba[6]=(anInstruction.pulseWidth) & 0xFF

        ba[7]=(anInstruction.decay>>8) & 0xFF
        ba[8]=(anInstruction.decay) & 0xFF
    
        ba[9]=(anInstruction.delay>>8) & 0xFF
        ba[10]=(anInstruction.delay) & 0xFF

        ba[11]=(anInstruction.maxTimeOn>>8) & 0xFF
        ba[12]=(anInstruction.maxTimeOn) & 0xFF

        for i in range(0,12):
            index=i*2+13
            ba[index] = (anInstruction.adjustedThresholds[i]>>8) & 0xFF            
            ba[index+1] = (anInstruction.adjustedThresholds[i]) & 0xFF                     
        self._AddChecksumFourBytes(0,ba)       
        
        encodedba=cobs.encode(ba)        
        barray = bytearray(encodedba)
        barray.append(0x00)         

        # Using the RT patched linus, it appears that 
        # a delay of 0.005 is just enough to transmit 43 bytes.
        self._WriteByteArray(barray,0.006)        
        tmp=self._Read(2)
        if(len(tmp)!=2):            
            return False
        if(tmp[0]==ID):
            return True 
        else:            
            return False    

    def GetStatusPacketUART(self,dfm):                      
        start = time.time()
        self.RequestStatus(dfm.ID)
        end=time.time()
        if ((end-start)>0.030) :
            print("Request time: "+str(end-start))        
        try:      
            ## This is set for maxpackets = 60
            return cobs.decode(self._ReadCOBSPacket(4000))
        except:
            return ''
    
    def PollSlaveUART(self,ID):          
        self.thePort.reset_input_buffer()
        ba = bytearray(3)
        ba[0]=ID
        ba[1]=0xFE # Indicates buffer reset        
        ba[2]=ID
    
        encodedba=cobs.encode(ba)        
        barray = bytearray(encodedba)
        barray.append(0x00)            
        self._WriteByteArray(barray,0.001)
       
        tmp=self._Read(2)         
        if(len(tmp)!=2):            
            return False
        if(tmp[0]==ID):
            return True
        else:
            return False                               
    #endregion    
    # 

    def PollSlave(self,ID,dfmtype):
        if(dfmtype==Enums.DFMTYPE.PLETCHERV3):
            return self.PollSlaveUART(ID)
        else:
            return self.PollSlaveI2C(ID)

    def GetStatusPacket(self,dfm):   
        if(dfm.DFMType==Enums.DFMTYPE.PLETCHERV3):
            return self.GetStatusPacketUART(dfm)
        else:
            return self.GetStatusPacketI2C(dfm)

    #region I2C
    def PollSlaveI2C(self,ID):     
        try:  
            tmp = 0x50+ID
            b = self.i2cbus.read_byte_data(tmp,1)            
            return ID            
        except:
            return ''
        #b = self.bus.read_i2c_block_data(tmp,1,16)
        #print(msg)
        

    def GetStatusPacketI2C(self,dfm):     
        tmp = 0x50+dfm.ID
        if dfm.DFMType == Enums.DFMTYPE.PLETCHERV2:
            bytestoget = 64
        elif dfm.DFMType == Enums.DFMTYPE.SABLEV2:
            bytestoget = 52
        try:
            msg = smbus2.i2c_msg.read(tmp,bytestoget)     
            self.i2cbus.i2c_rdwr(msg)            
            return list(msg)        
        except:
            return ''   

    def GoDarkI2C(self, dfm):
        try:
            tmp = 0x50+dfm.ID
            buffer = [1]
            self.i2cbus.write_i2c_block_data(tmp,1,buffer)
            return True
        except:
            return False

    def ExitDarkI2C(self, dfm):
        try:
            tmp = 0x50+dfm.ID
            buffer = [0x00]
            self.i2cbus.write_i2c_block_data(tmp,1,buffer)
            return True
        except:
            return False
    
    def SendOptoStateI2C(self,dfm, os1, os2):
        try:
            tmp = 0x50+dfm.ID
            buffer=[os1,os2]
            self.i2cbus.write_i2c_block_data(tmp,2,buffer)
            return True
        except:
            return False

    def SendFrequencyI2C(self,dfm, freq):
        try:
            tmp = 0x50+dfm.ID
            buffer=[freq]
            self.i2cbus.write_i2c_block_data(tmp,4,buffer)
            return True
        except:
            return False

    def SendPulseWidthI2C(self,dfm, pw):
        try:
            tmp = 0x50+dfm.ID
            buffer=[pw]
            self.i2cbus.write_i2c_block_data(tmp,5,buffer)            
            return True
        except:
            return False
    #endregion  
       

def ModuleTest5(dfmID):
    Board.BoardSetup()
    p=COMM()
    print(p.PollSlave(dfmID,Enums.DFMTYPE.PLETCHERV2))
    #p.GetStatusPacket(dfmID,Enums.DFMTYPE.PLETCHERV2)
    #print(p.GoDark(dfmID))
    #print(p.ExitDark(dfmID))


if __name__=="__main__" :
    ModuleTest5(6)   
    print("Done!!")     

#endregion
