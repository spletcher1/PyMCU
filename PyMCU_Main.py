import time
import _thread   
import DFMGroup 
import Enums
import datetime
import platform
import COMM
import sys
import Board

if("MCU" in platform.node()):
    import RPi.GPIO as GPIO

def main():
    if("MCU" in platform.node()):
        Board.BoardSetup()   
    ##tmp = DFMGroup.DFMGroup(COMM.UARTCOMM())
    tmp = DFMGroup.DFMGroup(COMM.TESTCOMM())
    print("Looking for DFM:")
    tmp.FindDFMs(2)    
    for d in tmp.theDFMs:
        print("DFMs Found ID: " + str(d.ID))       
    tmp.LoadSimpleProgram(datetime.datetime.today()+datetime.timedelta(minutes=1),datetime.timedelta(minutes=1*60))    
    #tmp.LoadTextProgram("TestProgram1.txt")
    print(tmp.currentProgram)
    tmp.StageCurrentProgram()
    counter=0
    while(tmp.currentProgram.isActive):           
        tmp.UpdateProgramStatus()             
        counter+=1
        time.sleep(1)
    tmp.StopReading()
    
def MiniMain():
    if("MCU" in platform.node()):
        Board.BoardSetup()   
    tmp = DFMGroup.DFMGroup(COMM.UARTCOMM())
    tmp.FindDFMs(2,False)
    if(len(tmp.theDFMs)<1):
        print("No DFM found!")
        return
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
