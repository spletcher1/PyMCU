import adafruit_si7021

class SI7021:
    def __init__(self,i2c):
        self.__Initialize(i2c)
    def __Initialize(self,i2c):
        self.theSensor=adafruit_si7021.SI7021(i2c)
    def GetTemperature(self):
        return self.theSensor.temperature
    def GetHumidity(self):
        return self.theSensor.relative_humidity
