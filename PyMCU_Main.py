import time
import _thread   
import DFMGroup 
import Enums
import datetime
import platform
import COMM

if(platform.node()=="raspberrypi"):
    import RPi.GPIO as GPIO


def BoardSetup():
    GPIO.setmode(GPIO.BCM)

    ledPIN=13
    relayPIN=6

    GPIO.setup(ledPIN,GPIO.OUT)
    GPIO.setup(relayPIN,GPIO.OUT)
    GPIO.output(relayPIN,GPIO.HIGH)
    GPIO.output(ledPIN,GPIO.HIGH)
    

def main():
    if(platform.node()=="raspberrypi"):
        BoardSetup()   
    theDFMs = DFMGroup.DFMGroup(COMM.TESTCOMM())
    theDFMs.FindDFMs()
    theDFMs.StartReading()


if __name__=="__main__" :
    main()
         
