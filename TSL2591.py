import adafruit_tsl2591

class TSL2591:
    def __init__(self,i2c):
        self.__Initialize(i2c)
    def __Initialize(self, i2c):
        self.theSensor = adafruit_tsl2591.TSL2591(i2c)
        if self.theSensor is not None:      
            # Enable the light sensor
            self.theSensor.enabled = True
            # Set default gain (LOW = 1; MED=25; HIGH=428; MAX=9876)
            self.theSensor.gain = adafruit_tsl2591.GAIN_MED 
            # Set integration time (intervals of 100ms)
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_300MS
    def Set100msIntegrationTime(self):
        self.theSensor.integration_time=adafruit_tsl2591.INTEGRATIONTIME_100MS
    def Set200msIntegrationTime(self):
        self.theSensor.integration_time=adafruit_tsl2591.INTEGRATIONTIME_200MS
    def Set300msIntegrationTime(self):
        self.theSensor.integration_time=adafruit_tsl2591.INTEGRATIONTIME_300MS
    def Set400msIntegrationTime(self):
        self.theSensor.integration_time=adafruit_tsl2591.INTEGRATIONTIME_400MS
    def Set500msIntegrationTime(self):
        self.theSensor.integration_time=adafruit_tsl2591.INTEGRATIONTIME_500MS
    def Set600msIntegrationTime(self):
        self.theSensor.integration_time=adafruit_tsl2591.INTEGRATIONTIME_600MS
    def SetGainLow(self):
        self.theSensor.gain = adafruit_tsl2591.GAIN_LOW
    def SetGainMedium(self):
        self.theSensor.gain = adafruit_tsl2591.GAIN_MED
    def SetGainHigh(self):
        self.theSensor.gain = adafruit_tsl2591.GAIN_HIGH
    def SetGainMax(self):
        self.theSensor.gain = adafruit_tsl2591.GAIN_MAX
    def PrintAllInfo(self):
            visible = self.theSensor.visible
            infrared = self.theSensor.infrared
            fullspectrum = self.theSensor.full_spectrum
            lux = self.GetLUX()
            if(lux != -99) : 
                print("Gain = {}".format(self.theSensor.gain))
                print("Integration time = {}".format(self.theSensor.integration_time))
                print("Visible Light = {}".format(visible))
                print("Infrared = {}".format(infrared))
                print("Full spectrum = {}".format(fullspectrum))
                print("Lux = {}".format(lux))
            else :
                print("Adjusting sensitivity...")

    def IncreaseSensitivity(self):       
        wasSensitivityIncreased=True
        if self.theSensor.gain == adafruit_tsl2591.GAIN_LOW :
            self.theSensor.gain = adafruit_tsl2591.GAIN_MED
        elif self.theSensor.gain == adafruit_tsl2591.GAIN_MED :
            self.theSensor.gain = adafruit_tsl2591.GAIN_HIGH
        elif self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_100MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_200MS
        elif self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_200MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_300MS
        elif self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_300MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_400MS
        elif self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_400MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_500MS
        else :
            wasSensitivityIncreased=False
        return wasSensitivityIncreased

    def DecreaseSensitivity(self):        
        wasSensitivityDecreased=True      
        if self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_500MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_400MS
        elif self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_400MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_300MS
        elif self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_300MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_200MS
        elif self.theSensor.integration_time == adafruit_tsl2591.INTEGRATIONTIME_200MS :
            self.theSensor.integration_time = adafruit_tsl2591.INTEGRATIONTIME_100MS
        elif self.theSensor.gain == adafruit_tsl2591.GAIN_HIGH :
            self.theSensor.gain = adafruit_tsl2591.GAIN_MED
        elif self.theSensor.gain == adafruit_tsl2591.GAIN_MED :
            self.theSensor.gain = adafruit_tsl2591.GAIN_LOW
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
            if(lux<1.0):
                if(self.IncreaseSensitivity()):
                    return -99                
                else:
                    return lux
            else:
                return lux
        # Circuitpython returns runtimeerror on overflow
        except RuntimeError: 
            if(self.DecreaseSensitivity()):
                return -99
            else:
                return 65000
            

