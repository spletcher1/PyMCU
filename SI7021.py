import adafruit_si7021
import board
import time
import smbus

class SI7021:
    def __init__(self):
        count=0
        while (count<5):
            try:
                self.__Initialize()                
                count=5
            except:
                count+=1                
    def __Initialize(self):        
        self.theSensor=adafruit_si7021.SI7021(board.I2C())
        
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

#region Module Testing

def ModuleTest():
    try:
        theSensor=adafruit_si7021.SI7021(board.I2C()) 
    except:
        theSensor=adafruit_si7021.SI7021(board.I2C()) 
    try:        
        while(1):
            print(theSensor.temperature)
            print(theSensor.relative_humidity)
            time.sleep(1)
    except:
        print("Except")
    
def ModuleTest2():
    # Get I2C bus
    bus = smbus.SMBus(1)
    bus.write_byte(0x40, 0xF5)
    
    time.sleep(0.3)
    
    # SI7021 address, 0x40  Read 2 bytes, Humidity
    data0 = bus.read_byte(0x40)
    data1 = bus.read_byte(0x40)
    
    # Convert the data
    humidity = ((data0 * 256 + data1) * 125 / 65536.0) - 6
    
    time.sleep(0.3)
    bus.write_byte(0x40, 0xF3)
    time.sleep(0.3)
    
    # SI7021 address, 0x40 Read data 2 bytes, Temperature
    data0 = bus.read_byte(0x40)
    data1 = bus.read_byte(0x40)
    
    # Convert the data and output it
    celsTemp = ((data0 * 256 + data1) * 175.72 / 65536.0) - 46.85
    fahrTemp = celsTemp * 1.8 + 32
    
    print(humidity)
    print(celsTemp)
    print(fahrTemp)
    
       
if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     

#endregion