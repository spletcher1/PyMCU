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

if(platform.system()!="Windows"):
    import serial.tools.list_ports

if(platform.node()=="raspberrypi"):        
    import RPi.GPIO as GPIO

class TESTCOMM():
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
    def _CreateFakeStatusPacket(self,ID):
        tmp = StatusPacket.StatusPacket(0)
        ba = bytearray(65)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x00 #Error flag     
        for i in range(0,12):
            analog=50+randint(0,20)
            analog *=128
            ba[(3*i)+5]=analog >> 16
            ba[(3*i)+6]=(analog >> 8) & 0xFF
            ba[(3*i)+7]=analog & 0xFF
        
        voltsin = int((2.5/3.3)*1024*128)
        ba[41] = voltsin>>16
        ba[42] = (voltsin>>8) & 0xFF
        ba[43] = voltsin & 0xFF
         
        ba[44]=0x00 #OS1
        ba[45]=0x00 #OS2

        ba[46]=0x00 #Freq
        ba[47]=0x28

        ba[48]=0x00 #PW
        ba[49]=0x08

        ba[50]=0x00 # Dark mode

        tmp = 18 + randint(0,10) 
        tmp*=1000
        ba[51] = tmp>>24
        ba[52] = (tmp>>16) & 0xFF
        ba[53] = (tmp>>8) & 0xFF
        ba[54] = tmp & 0xFF

        tmp = 45 + randint(0,20) 
        tmp*=1000
        ba[55] = tmp>>24
        ba[56] = (tmp>>16) & 0xFF
        ba[57] = (tmp>>8) & 0xFF
        ba[58] = tmp & 0xFF

        tmp = 500 + randint(0,80) 
        ba[59] = (tmp>>8) & 0xFF
        ba[60] = tmp & 0xFF

        calculatedCheckSum=0
        for cs in range(3,len(ba)-4) :
            calculatedCheckSum+=ba[cs]
        calculatedCheckSum = (calculatedCheckSum ^ 0xFFFFFFFF) + 0x01
        ba[61] = calculatedCheckSum>>24
        ba[62] = (calculatedCheckSum>>16) & 0xFF
        ba[63] = (calculatedCheckSum>>8) & 0xFF
        ba[64] = calculatedCheckSum & 0xFF

        return ba
    def GetStatusPacket(self,ID):        
        tmp = self._CreateFakeStatusPacket(ID) 
        return tmp


class UARTCOMM():    
    UART_message = Event.Event()
    def __init__(self):
        self.thePort=serial.Serial('/dev/ttyAMA0',115200,timeout=1)           
        self.sendPIN = 17
        GPIO.setup(self.sendPIN,GPIO.OUT)        
        GPIO.output(self.sendPIN,GPIO.LOW)
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        UARTCOMM.UART_message.notify(tmp)   
    def _Write(self,s):
        GPIO.output(self.sendPIN,GPIO.HIGH)       
        self.thePort.write(s.encode())        
        time.sleep(0.005)
        GPIO.output(self.sendPIN,GPIO.LOW)
    def _WriteByteArray(self,ba):       
        GPIO.output(self.sendPIN,GPIO.HIGH)
        self.thePort.write(ba)
        time.sleep(0.001)
        GPIO.output(self.sendPIN,GPIO.LOW)
    def _SetShortTimeout(self):
        self.thePort.timeout=0.1
    def _ResetTimeout(self):
        self.thePort.timeout=1
    def _Read(self,numBytes):
        result=self.thePort.read(numBytes)
        return result
    def _ReadCOBSPacket(self, maxBytes):
        term = bytearray(1)
        term[0]=0x00
        result = self.thePort.read_until(term,maxBytes)
        result = result[:-1]
        return result
    def GetAvailablePorts(self):
        ports = serial.tools.list_ports.comports()
        available_ports=[]
        for p in ports:
            available_ports.append(p.device)
        return available_ports    
    def _AddChecksumTwoBytes(self, bytes):
        checksum=0
        tmp = len(bytes)
        for i in range(0,tmp-2):
            checksum=checksum+bytes[i]
        checksum = (checksum ^ 0xFFFFFFFF) + 0x01
        checksum = checksum & 0x0000FFFF
        bytes[tmp-2] = (checksum>>8) & 0xFF
        bytes[tmp-1] = (checksum) & 0xFF
    def RequestStatus(self,ID):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x01
        ba[5]=0x01
        ba[6]=0x01
        ba[7]=0x01
        ba[8]=0x01
        self._WriteByteArray(ba)
    def SendOptoState(self, os1, os2,ID):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x03
        ba[5]=os1
        ba[6]=os2
        self._AddChecksumTwoBytes(ba)       
        self._WriteByteArray(ba)
    def SendPulseWidth(self, pw,ID):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x05
        ba[5]=(pw>>8) & 0xFF
        ba[6]= (pw & 0xFF)
        self._AddChecksumTwoBytes(ba)
        self._WriteByteArray(ba)
    def SendFrequency(self,freq,ID):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x04
        ba[5]=(freq>>8) & 0xFF
        ba[6]= (freq & 0xFF)
        self._AddChecksumTwoBytes(ba)
        self._WriteByteArray(ba)
    def GoDark(self,ID):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x02
        ba[5]=0x01
        ba[6]=0x01
        self._AddChecksumTwoBytes(ba)
        self._WriteByteArray(ba)      
    def ExitDark(self,ID):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x02
        ba[5]=0x00
        ba[6]=0x01
        self._AddChecksumTwoBytes(ba)
        self._WriteByteArray(ba)  
    def GetStatusPacket(self,ID):
        self.RequestStatus(ID)
        return self._Read(65) 
    def PollSlave(self,ID):
        ba = bytearray(9)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        ba[4]=0x06
        ba[5]=0x01
        ba[6]=0x01
        ba[7]=0x01
        ba[8]=0x01        
        self._SetShortTimeout()    
        self._WriteByteArray(ba)          
        tmp=self._Read(1)
        self._ResetTimeout()
        if(len(tmp)==0):         
            return False
        elif(tmp[0]==ID) :
            return True
        else :            
            return False
