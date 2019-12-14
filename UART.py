import time
import _thread 
import socketserver 
import serial
import serial.tools.list_ports
import RPi.GPIO as GPIO



class MyUART:    
    def __init__(self):
        self.thePort=serial.Serial('/dev/serial0',115200,timeout=1)           
        self.sendPIN = 19
        GPIO.setup(self.sendPIN,GPIO.OUT)
        GPIO.output(self.sendPIN,GPIO.LOW)
    def Write(self,s):
        GPIO.output(self.sendPIN,GPIO.HIGH)
        self.thePort.write(s.encode())
        time.sleep(0.005)
        GPIO.output(self.sendPIN,GPIO.LOW)
    def WriteByteArray(self,ba):
        GPIO.output(self.sendPIN,GPIO.HIGH)
        self.thePort.write(ba)
        time.sleep(0.005)
        GPIO.output(self.sendPIN,GPIO.LOW)
    def SetShortTimeout(self):
        self.thePort.timeout=0.1
    def ResetTimeout(self):
        self.thePort.timeout=3
    def Read(self,numBytes):
        result=self.thePort.read(numBytes)
        return result
    def ReadCOBSPacket(self, maxBytes):
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
