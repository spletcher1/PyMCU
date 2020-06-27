import busio
import board
import time
import TSL2591
import SI7021


class EnvironmentalMonitor():
    def __init__(self,uartID):
        self.uartID = uartID
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.tsl = TSL2591.TSL2591(self.i2c)
        self.si =  SI7021.SI7021(self.i2c)  
        self.light=0
        self.humidity=0
        self.temperature=0 
    def UpdateReadings(self):
        testing=False
        if(testing==False):
            self.temperature=self.si.GetTemperature()
            l=self.tsl.GetLUX()
            counter=0
            while (l == -99 and counter<10) :
                l=self.tsl.GetLUX()
                time.sleep(1)
                counter+=1
            self.light = l
            self.humidity=self.si.GetHumidity()
        else:
            self.light=100
            self.humidity=50
            self.temperature=25
        
        
