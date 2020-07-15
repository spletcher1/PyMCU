import busio
import board
import time
import TSL2591
import SI7021
from enum import Enum

class MonitorState(Enum):
    IDLE=1,
    REQUESTTEMP=2
    GETTEMP=3
    REQUESTHUM=4
    GETHUM=5
    GETLIGHT=6

# pip3 install adafruit-blinka
# pip3 install adafruit-circuitpython-tsl2591
# pip3 install adafruit-circuitpython-si7021
class EnvironmentalMonitor():
    def __init__(self,stepsinidle): 
        self.stepsInIdle=stepsinidle 
        self.isPresent=False  
        self.Initialize()       
    
    def Initialize(self):
        try: 
            self.currentState=MonitorState.IDLE               
            self.currentIdleSteps=0
            self.light=0
            self.humidity=0
            self.temperature=0            
            self.i2c = busio.I2C(board.SCL, board.SDA)
            self.tsl = TSL2591.TSL2591(self.i2c)
            self.si =  SI7021.SI7021(self.i2c)                      
            self.isPresent=True                
        except:            
            self.tsl=None
            self.si = None
            self.isPresent=False


    def StepMonitor(self):       
        if(self.isPresent==False):
            self.currentState==MonitorState.IDLE
            return
        try:
            if (self.currentState==MonitorState.IDLE):          
                self.currentIdleSteps+=1
                if(self.currentIdleSteps>=self.stepsInIdle):                
                    self.currentIdleSteps=0
                    self.currentState = MonitorState.REQUESTTEMP
            elif (self.currentState==MonitorState.REQUESTTEMP):
                self.si.StartTemperatureMeasurement()
                self.currentState = MonitorState.GETTEMP
            elif (self.currentState==MonitorState.GETTEMP):
                self.temperature = self.si.GetTemperature()
                self.currentState = MonitorState.REQUESTHUM
            elif (self.currentState == MonitorState.REQUESTHUM):
                self.si.StartHumidityMeasurement()
                self.currentState = MonitorState.GETHUM
            elif(self.currentState==MonitorState.GETHUM):
                self.humidity = self.si.GetHumidity()  
                self.currentState = MonitorState.GETLIGHT
            elif(self.currentState==MonitorState.GETLIGHT):
                self.light=self.tsl.GetLUX()
                if(self.light!=-99):
                    self.currentState = MonitorState.IDLE   
        except:
            print("Environmental monitor lost.")
            self.isPresent=False
            self.light=0
            self.humidity=0
            self.temperature=0      
            self.currentState==MonitorState.IDLE
            return


    def UpdateReadings(self):
        testing=False
        self.temperature=-1
        self.light=-1
        self.temperature=-1        
        if(testing==False):
            try:
                self.temperature=self.si.GetTemperature()            
                self.light =self.tsl.GetLUX()
                self.humidity=self.si.GetHumidity()            
            except:
                return            
        else:
            self.light=100
            self.humidity=50
            self.temperature=25
    
    def __str__(self):
        s = "Temp: "+str(self.temperature)+"  Light: "+str(self.light)+"  Humidity: "+str(self.humidity)
        return s
        
        
#region Module Testing

def ModuleTest():
   tmp = EnvironmentalMonitor(10)
   while(True):
       tmp.StepMonitor()
       time.sleep(0.1)
   
       
if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     

#endregion