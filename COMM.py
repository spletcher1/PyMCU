import platform
import Event
import Message
import datetime
import Instruction
import Enums
import Board
import smbus2
import time
import serial
from cobs import cobs

if(platform.system()!="Windows"):
    import serial.tools.list_ports

if("MCU" in platform.node()):        
    import RPi.GPIO as GPIO


class UARTCOMM():    
    UART_message = Event.Event()
    #region Core read/write functions
    def __init__(self):
        ## The timeout here is tricky.  For 15 packets to be sent, it seems to
        ## take about 0.150 seconds, so the timeout has to be larger than this
        ## or the packet gets cut off.
        self.thePort=serial.Serial('/dev/ttyAMA0',115200,timeout=.3)           
        self.sendPIN = 17
        GPIO.setup(self.sendPIN,GPIO.OUT)        
        GPIO.output(self.sendPIN,GPIO.LOW)
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        UARTCOMM.UART_message.notify(tmp)   
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
    
    def RequestBufferReset(self,ID):        
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
    def SendLinkage(self,ID,linkage):
        ba = bytearray(18)
        ba[0]=ID
        ba[1]=0xFB
        for i in range(0,12):
            ba[i+2]=linkage[i]
        self._AddChecksumFourBytes(0,ba)
        encodedba=cobs.encode(ba)        
        barray = bytearray(encodedba)
        barray.append(0x00)        
        self._WriteByteArray(barray,0.006)        
        tmp=self._Read(2)
        if(len(tmp)!=2):            
            return False
        if(tmp[0]==ID):
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

    def GetStatusPacket(self,ID,dummy):                      
        start = time.time()
        self.RequestStatus(ID)
        end=time.time()
        if ((end-start)>0.030) :
            print("Request time: "+str(end-start))        
        try:      
            ## This is set for maxpackets = 60
            return cobs.decode(self._ReadCOBSPacket(4000))
        except:
            return ''
    def PollSlave(self,ID): 
        if self.RequestBufferReset(ID):                      
            return Enums.DFMTYPE.PLETCHERV3
        else:
            return ''
    #endregion     
       


class I2CCOMM():      
    def __init__(self):
        self.i2cbus = smbus2.SMBus(1)
      
    def PollSlave(self,ID):
        bytestoget = 64         
        try:
            tmpAddr = 0x50+ID         
            msg=smbus2.i2c_msg.read(tmpAddr,bytestoget)
            self.i2cbus.i2c_rdwr(msg)       
            tmp=list(msg)
            if((tmp[60]+tmp[61]+tmp[62]+tmp[63])==0):
                return Enums.DFMTYPE.SABLEV2
            else:
                return Enums.DFMTYPE.PLETCHERV2
        except:
            return ''
        
    def GetStatusPacket(self,ID,DFMType):
        if(DFMType == Enums.DFMTYPE.PLETCHERV2):             
            bytestoget = 64               
        elif(DFMType == Enums.DFMTYPE.SABLEV2):             
            bytestoget = 52               
        else:
            bytestoget = 64               
        try:                     
            tmpAddr = 0x50+ID         
            msg=smbus2.i2c_msg.read(tmpAddr,bytestoget)
            self.i2cbus.i2c_rdwr(msg)            
            return list(msg)                
        except:
            print("Get Status I2C Error")
            return ''   

    def SendDark(self,ID,darkstate):
        try:
            tmpAddr = 0x50+ID   
            buffer = [darkstate]
            self.i2cbus.write_i2c_block_data(tmpAddr,1,buffer)                  
            return True
        except:
            return False

    def SendOptoState(self, ID, os1, os2):
        try:
            tmpAddr = 0x50+ID   
            buffer=[os1,os2]
            self.i2cbus.write_i2c_block_data(tmpAddr,2,buffer)            
            return True
        except:
            return False

    def SendFrequency(self, ID, freq):
        try:
            tmpAddr = 0x50+ID         
            buffer = [freq]
            self.i2cbus.write_i2c_block_data(tmpAddr,4,buffer)                 
            return True
        except:
            return False

    def SendPulseWidth(self,ID,pw):
        try:
            tmpAddr = 0x50+ID         
            buffer = [pw]
            self.i2cbus.write_i2c_block_data(tmpAddr,5,buffer)                 
            return True
        except:
            return False
       

def ModuleTest5(dfmID):
    Board.BoardSetup()
   

if __name__=="__main__" :
    theCOMM = I2CCOMM()    
    theCOMM.SetDark(0x06,0)
   