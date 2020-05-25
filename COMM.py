import platform
import Event
import Message
import datetime
import Instruction
import Enums
import Board
import smbus2

if(platform.system()!="Windows"):
    import serial.tools.list_ports

if("MCU" in platform.node()):        
    import RPi.GPIO as GPIO

class I2CCOMM():      
    def __init__(self):
        self.i2cbus = smbus2.SMBus(1)
      
    def PollSlave(self,ID):
        bytestoget = 64         
        try:
            tmpAddr = 0x50+ID         
            msg=smbus2.i2c_msg.read(tmpAddr,bytestoget)
            self.i2cbus.i2c_rdwr(msg)            
            return ID                
        except:
            return ''
        
    def GetStatusPacket(self,ID):             
        bytestoget = 64               
        try:                     
            tmpAddr = 0x50+ID         
            msg=smbus2.i2c_msg.read(tmpAddr,bytestoget)
            self.i2cbus.i2c_rdwr(msg)            
            return list(msg)                
        except:
            print("Get Status I2C Error")
            return ''   

    def SetDark(self,ID,darkstate):
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

    def SendPulseWidth(self,pw):
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
   