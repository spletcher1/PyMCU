import adafruit_tsl2561
import time

class TSL2561:
    def __init__(self,i2c):
        self.__Initialize(i2c)
    def __Initialize(self, i2c):        
        self.theSensor = adafruit_tsl2561.TSL2561(i2c)       
        if self.theSensor is not None:                  
            # Enable the light sensor
            self.theSensor.enabled = True
            # Set default gain (LOW = 0; HIGH=1)
            # High is 16x.
            self.theSensor.gain = 0 
            # Set integration time (For TSL2561, it can be 0, 1 or 2.)
            # This corresponds to 13.7ms, 101ms, and 402ms, respectively.
            # Start with low gain and medium integration time.
            self.theSensor.integration_time = 1
            self.isAtMaxSensitivity = False
            self.isAtMinSensitivity = False        
    def SetShortIntegrationTime(self):
        self.theSensor.integration_time=0
    def SetMediumIntegrationTime(self):
        self.theSensor.integration_time=1
    def SetLongIntegrationTime(self):
        self.theSensor.integration_time=2
    def PrintAllInfo(self):
        #Get raw (luminosity) readings individually
        visible = self.theSensor.broadband
        infrared = self.theSensor.infrared        
        # Get raw (luminosity) readings using tuple unpacking
        #broadband, infrared = tsl.luminosity
        # Get computed lux value (tsl.lux can return None or a float)
        lux = self.GetLUX()
        if(lux != -99) : 
            print("Gain = {}".format(self.theSensor.gain))
            print("Integration time = {}".format(self.theSensor.integration_time))
            print("Visible Light = {}".format(visible))
            print("Infrared = {}".format(infrared))          
            print("Lux = {}".format(lux))
        else :
            print("Adjusting sensitivity...")
    def SetHighGain(self):
        self.theSensor.gain=0
    def SetLowGain(self):
        self.theSensor.gain=1
    
    def IncreaseSensitivity(self):       
        wasSensitivityIncreased=True
        if self.theSensor.integration_time == 0 :
            self.theSensor.integration_time = 1
        elif self.theSensor.integration_time == 1 :
            self.theSensor.integration_time = 2
        elif self.theSensor.gain == 0:
            self.theSensor.gain = 1
        else :
            wasSensitivityIncreased=False

        return wasSensitivityIncreased

    def DecreaseSensitivity(self):        
        wasSensitivityDecreased=True      
        if self.theSensor.gain == 1 :
            self.theSensor.gain = 0      
        elif self.theSensor.integration_time == 2 :
            self.theSensor.integration_time = 1
        elif self.theSensor.integration_time == 1 :
            self.theSensor.integration_time = 0
        else:
            wasSensitivityDecreased=False
        return wasSensitivityDecreased
    
    def GetLUX(self):
        if self.theSensor is None:
            return -1
        try:
            lux = self.theSensor.lux
            # returning -99 will ensure the state machine does not move on
            # and will call light again next step.
            if(lux is None):
                if(self.DecreaseSensitivity()):
                    return -99
                else:
                    return 65000    
            if(lux<1.0):
                if(self.IncreaseSensitivity()):
                    return -99                
                else:
                    return lux
            else:
                return lux
        # Circuitpython may return runtimeerror on overflow
        except RuntimeError: 
            if(self.DecreaseSensitivity()):
                return -99
            else:
                return 65000
        
  