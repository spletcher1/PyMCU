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
        ba = bytearray(309)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        for j in range(0,5):
            indexer = (j*61)+4
            ba[indexer]=0x00 #Error flag     
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

            calculatedCheckSum=0
            for cs in range(indexer,indexer+57) :
                calculatedCheckSum+=ba[cs]
            calculatedCheckSum = (calculatedCheckSum ^ 0xFFFFFFFF) + 0x01
            ba[(indexer+57)] = calculatedCheckSum>>24
            ba[(indexer+58)] = (calculatedCheckSum>>16) & 0xFF
            ba[(indexer+59)] = (calculatedCheckSum>>8) & 0xFF
            ba[(indexer+60)] = calculatedCheckSum & 0xFF

        return ba
    def GetStatusPacket(self,ID):        
        tmp = self._CreateFakeStatusPacket(ID) 
        return tmp


class UARTCOMM():    
    UART_message = Event.Event()
    def __init__(self):
        self.thePort=serial.Serial('/dev/ttyAMA0',115200,timeout=2)           
        self.sendPIN = 17
        GPIO.setup(self.sendPIN,GPIO.OUT)        
        GPIO.output(self.sendPIN,GPIO.LOW)
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        UARTCOMM.UART_message.notify(tmp)   
    def _Write(self,s):
        GPIO.output(self.sendPIN,GPIO.HIGH)       
        self.thePort.write(s.encode())                
        GPIO.output(self.sendPIN,GPIO.LOW)
    def _WriteByteArray(self,ba):       
        GPIO.output(self.sendPIN,GPIO.HIGH)
        self.thePort.write(ba)        
        GPIO.output(self.sendPIN,GPIO.LOW)
    def _SetShortTimeout(self):
        self.thePort.timeout=0.1
    def _ResetTimeout(self):
        self.thePort.timeout=2
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
        start = time.time()
        GPIO.output(self.sendPIN,GPIO.HIGH)
        self.thePort.write(ba)        
        GPIO.output(self.sendPIN,GPIO.LOW)
        #self.RequestStatus(ID)
        end=time.time()

        if ((end-start)>0.00000001) :
            print(str(datetime.datetime.today())+" "+str(end-start))
        
        #Read 5 packets at once!
        # 4 without header = 309 total
        return self._Read(309) 
        #return tmp 
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
