import adafruit_si7021

class SI7021:
    def __init__(self,i2c):
        self.__Initialize(i2c)
    def __Initialize(self,i2c):
        self.theSensor=adafruit_si7021.SI7021(i2c)
    def GetTemperature(self):
        if self.theSensor is None:
            return -1
        value = self.theSensor._data()
        self.theSensor._measurement = 0
        return value * 175.72 / 65536.0 - 46.85        
    def GetHumidity(self):
        if self.theSensor is None:
            return -1
        value = self.theSensor._data()
        self.theSensor._measurement = 0
        return min(100.0, value * 125.0 / 65536.0 - 6.0)
    def StartTemperatureMeasurement(self):
        self.theSensor.start_measurement(0xF3)
    def StartHumidityMeasurement(self):
        self.theSensor.start_measurement(0xF5)
