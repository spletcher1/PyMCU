import time
import _thread   
import RPi.GPIO as GPIO
import DFMGroup 
import Enums
import datetime

def BoardSetup():
    GPIO.setmode(GPIO.BCM)

    ledPIN=13
    relayPIN=6

    GPIO.setup(ledPIN,GPIO.OUT)
    GPIO.setup(relayPIN,GPIO.OUT)
    GPIO.output(relayPIN,GPIO.HIGH)
    GPIO.output(ledPIN,GPIO.HIGH)
    

def main():
    BoardSetup()   
    theDFMs = DFMGroup.DFMGroup()
    theDFMs.FindDFMs()
    theDFMs.StartReading()


if __name__=="__main__" :
    main()
         
