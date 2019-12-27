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

if(platform.system()!="Windows"):
    import serial.tools.list_ports

if(platform.node()=="raspberrypi"):        
    import RPi.GPIO as GPIO

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
    def _CreateFakeStatusPacket(self,ID):
        tmp = StatusPacket.StatusPacket(0)
        ba = bytearray(329)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        for j in range(0,5):
            indexer = (j*65)+4
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

            tmp = self.recordIndex
            ba[(indexer+57)] = tmp>>24
            ba[(indexer+58)] = (tmp>>16) & 0xFF
            ba[(indexer+59)] = (tmp>>8) & 0xFF
            ba[(indexer+60)] = tmp & 0xFF
            
            calculatedCheckSum=0
            for cs in range(indexer,indexer+61) :
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


class UARTCOMM():    
    UART_message = Event.Event()
    def __init__(self):
        self.thePort=serial.Serial('/dev/ttyAMA0',115200,timeout=.1)           
        self.sendPIN = 17
        GPIO.setup(self.sendPIN,GPIO.OUT)        
        GPIO.output(self.sendPIN,GPIO.LOW)
    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        UARTCOMM.UART_message.notify(tmp)   
    def _Write(self,s,delay=0.005):
        GPIO.output(self.sendPIN,GPIO.HIGH)       
        self.thePort.write(s.encode())               
        time.sleep(delay)     
        GPIO.output(self.sendPIN,GPIO.LOW)
    def _WriteByteArray(self,ba,delay=0.005):       
        GPIO.output(self.sendPIN,GPIO.HIGH)
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
    def RequestStatus(self,ID):
        ba = bytearray(5)
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFC # Indicates status request
        ba[3]=ID
        ba[4]=ID
        self._WriteByteArray(ba,0.001)
    def SendInstruction(self,ID,anInstruction):
        ba = bytearray(43)   
        ba[0]=0xFF
        ba[1]=0xFF
        ba[2]=0xFD
        ba[3]=ID
        if(anInstruction.theDarkState==Enums.DARKSTATE.ON):
            ba[4]=1
        else:
            ba[4]=0
        ba[5]=(anInstruction.frequency>>8) & 0xFF
        ba[6]=(anInstruction.frequency) & 0xFF

        ba[7]=(anInstruction.pulseWidth>>8) & 0xFF
        ba[8]=(anInstruction.pulseWidth) & 0xFF

        ba[9]=(anInstruction.decay>>8) & 0xFF
        ba[10]=(anInstruction.decay) & 0xFF
    
        ba[11]=(anInstruction.delay>>8) & 0xFF
        ba[12]=(anInstruction.delay) & 0xFF

        ba[13]=(anInstruction.maxTimeOn>>8) & 0xFF
        ba[14]=(anInstruction.maxTimeOn) & 0xFF

        for i in range(0,12):
            index=i*2+15
            ba[index] = (anInstruction.optoValues[i]>>8) & 0xFF            
            ba[index+1] = (anInstruction.optoValues[i]) & 0xFF             
        
        self._AddChecksumFourBytes(3,ba)       
        # Using the RT patched linus, it appears that 
        # a delay of 0.005 is just enough to transmit 43 bytes.
        self._WriteByteArray(ba,0.006)

        tmp=self._Read(1)
        if(len(tmp)==0):
            return False
        if(tmp[0]==ID):
            return True
        else:
            return False    


    def GetStatusPacket(self,ID):                  
        start = time.time()
        self.RequestStatus(ID)
        end=time.time()
        if ((end-start)>0.005) :
            print(str(datetime.datetime.today())+" "+str(end-start))        
        #Now reading five packets.
        return self._Read(329) 
        #return tmp 
    def PollSlave(self,ID):
        tmp=self.GetStatusPacket(ID)        
        if(len(tmp)==329 and tmp[3]==ID):         
            return True
        else :            
            return False




def ModuleTest():
    Board.BoardSetup()
    p=UARTCOMM()
    inst = Instruction.DFMInstruction()
    inst.frequency=2
    inst.pulseWidth=500
    inst.maxTimeOn=1000
    inst.decay=2500
    inst.delay=1234
    for i in range(0,12):
        inst.SetOptoValueWell(i,i*3)
    #print(p.PollSlave(1))
    #time.sleep(1)
    #tmp = p.GetStatusPacket(1)
    #print(str(tmp))
    #time.sleep(1)
    print(p.SendInstruction(1,inst))    
    time.sleep(2)
    return
    for i in range(0,12):
        inst.optoValues[i]=-1
    print(p.SendInstruction(1,inst))    
    time.sleep(2)
    for i in range(0,12):
        inst.optoValues[i]=100
    inst.frequency=2
    inst.pulseWidth=500
    inst.maxTimeOn=1000
    print(p.SendInstruction(1,inst)        )

    
    


    


if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     