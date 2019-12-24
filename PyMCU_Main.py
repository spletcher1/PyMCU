import time
import _thread   
import DFMGroup 
import Enums
import datetime
import platform
import COMM
import sys

if(platform.node()=="raspberrypi"):
    import RPi.GPIO as GPIO


def BoardSetup():
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)

    ledPIN=13
    relayPIN=6

    GPIO.setup(ledPIN,GPIO.OUT)
    GPIO.setup(relayPIN,GPIO.OUT)
    GPIO.output(relayPIN,GPIO.HIGH)
    GPIO.output(ledPIN,GPIO.HIGH)
    
def ModuleTest():
    #tmp = DFMGroup(COMM.TESTCOMM())
    tmp = DFMGroup(COMM.UARTCOMM())
    tmp.FindDFMs(4)
    tmp.LoadSimpleProgram(datetime.datetime.today(),datetime.timedelta(minutes=1))
    print(tmp.currentProgram)
    tmp.ActivateCurrentProgram()
    while(tmp.currentProgram.isActive):   
        tmp.UpdateDFMStatus()     
        print(tmp.longestQueue)
        time.sleep(1)

def main():
    if(platform.node()=="raspberrypi"):
        BoardSetup()   
    tmp = DFMGroup.DFMGroup(COMM.UARTCOMM())
    ##tmp = DFMGroup.DFMGroup(COMM.TESTCOMM())
    tmp.FindDFMs(2)
    for d in tmp.theDFMs:
        print("DFMs Found ID: " + str(d.ID))       
    tmp.LoadSimpleProgram(datetime.datetime.today(),datetime.timedelta(minutes=360))    
    #tmp.LoadTextProgram("TestProgram2.txt")
    print(tmp.currentProgram)
    tmp.ActivateCurrentProgram()
    counter=0
    while(tmp.currentProgram.isActive):           
        tmp.UpdateDFMStatus()     
        #print("("+str(counter)+") " + str(tmp.theDFMs[0].currentStatusPacket.errorFlags))
        counter+=1
        time.sleep(1)
    tmp.StopReading()
    
def MiniMain():
    if(platform.node()=="raspberrypi"):
        BoardSetup()   
    tmp = DFMGroup.DFMGroup(COMM.UARTCOMM())
    tmp.FindDFMs(2,False)
    for d in tmp.theDFMs:
        print("DFMs Found ID: " + str(d.ID))
    tt = datetime.datetime.today()
    lastSecond=tt.second   
    while(1):
        tt = datetime.datetime.today()
        if(tt.microsecond>0 and tt.second != lastSecond): 
            tmp.theDFMs[0].ReadValues(datetime.datetime.today(),False)
            lastSecond=tt.second
            #for i in range(0,5):
            print(tmp.theDFMs[0].currentStatusPackets[0].GetConsolePrintPacket())        
        

if __name__=="__main__" :
    main()
    print("Done!!")  
    sys.exit()        
