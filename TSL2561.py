import adafruit_tsl2561
import time

class TSL2561:
    def __init__(self,i2c):
        self.__Initialize(i2c)
    def __Initialize(self, i2c):
        self.theSensor = adafruit_tsl2561.TSL2561(i2c)
        self.theSensor.enabled=True
        # Enable the light sensor
        self.theSensor.enabled = True
        # Set gain 0=16x, 1=1x
        self.theSensor.gain = 0 
        # Set integration time (0=13.7ms, 1=101ms, 2=402ms, or 3=manual)
        self.theSensor.integration_time = 1
    def SetShortIntegrationTime(self):
        self.theSensor.integration_time=0
    def SetMediumIntegrationTime(self):
        self.theSensor.integration_time=1
    def SetLongIntegrationTime(self):
        self.theSensor.integration_time=2
    def PrintAllInfo(self):
        #Get raw (luminosity) readings individually
        visible = self.theSensor.visible
        infrared = self.theSensor.infrared
        fullspectrum = self.theSensor.fullspectrum
        # Get raw (luminosity) readings using tuple unpacking
        #broadband, infrared = tsl.luminosity
        # Get computed lux value (tsl.lux can return None or a float)
        lux = self.theSensor.lux
        print("Gain = {}".format(self.theSensor.gain))
        print("Integration time = {}".format(self.theSensor.integration_time))
        print("Visible Light = {}".format(visible))
        print("Infrared = {}".format(infrared))
        print("Full spectrum = {}".format(fullspectrum))
        if lux is not None:
            print("Lux = {}".format(lux))
        else:
            print("Lux value is None. Possible sensor underrange or overrange.") 
    def SetHighGain(self):
        self.theSensor.gain=0
    def SetLowGain(self):
        self.theSensor.gain=1
    def GetLUX(self):
        lux = self.theSensor.lux
        if(lux=="None"):
            if(self.theSensor.gain==0):
                self.SetLowGain()
            elif(self.theSensor.gane==1):
                self.SetHighGain()                
            time.sleep(0.5)
            lux = self.theSensor.lux
        return lux