from multiprocessing import Queue, Process
import queue
import COMM
import datetime
import StatusPacket
import Enums
import math
import Board
import time
import sys

class MP_Message:
    def __init__(self,message):
        self.time = datetime.datetime.today()
        self.message=message

class MP_Command:
    def __init__(self,ctype,arg):
        self.commandType = ctype
        self.arguments=arg


class DataGetterUART:
    def __init__(self):
        self.data_q=Queue()
        self.message_q=Queue()
        self.command_q=Queue()   
        self.currentStatusPacket = StatusPacket.StatusPacket(0,0,Enums.DFMTYPE.SABLEV2) 
        self.DFMInfos = []                
        self.verbose=False
        self.theReader=None  
        self.theCOMM = COMM.I2CCOMM()
    def FindDFM(self, maxNum):   
        return []     

class DFMInfo:
    def __init__(self,id,dfmtype):
        self.ID = id
        self.DFMType=dfmtype

class DataGetterI2C:
    def __init__(self):
        #COMM.COMM.COMM_message+=self.NewMessageDirect
        self.data_q=Queue()
        self.message_q=Queue()
        self.command_q=Queue()       
        self.currentStatusPacket = StatusPacket.StatusPacket(0,0,Enums.DFMTYPE.SABLEV2)                          
        self.theCOMM = COMM.I2CCOMM()
        self.DFMInfos = []                
        self.verbose=False
        self.theReader=None

    # Remember that any variables set at the time of process forking can not be changed except
    # Through a queue.
    def FindDFM(self, maxNum):      
        self.DFMInfos.clear()
        for i in range(1,maxNum+1):
            tmp = self.theCOMM.PollSlave(i)
            if(tmp != '' ): 
                self.DFMInfos.append(DFMInfo(i,tmp))                        
            time.sleep(0.1)
        if(len(self.DFMInfos) > 0):
            self.StartReading()
        return self.DFMInfos

    def StopReading(self,block=True):   
        self.QueueMessage("Reader termination requested.")         
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.STOP_READING,''))        
        if(self.theReader is not None):
            while self.theReader.is_alive():
                pass
    
    def ClearQueuesInternal(self):
        try:
            while True:
                self.message_q.get_nowait()
        except queue.Empty:
            pass
        try:
            while True:
                self.command_q.get_nowait()
        except queue.Empty:
            pass
        try:
            while True:
                self.data_q.get_nowait()
        except queue.Empty:
            pass
        
    def ClearQueues(self):
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.CLEAR_ALLQ,''))
    def PauseReading(self):
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.PAUSE_READING,''))
    def ResumeReading(self):
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.RESUME_READING,''))
    def StartReading(self):        
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.PAUSE_READING,''))
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.CLEAR_ALLQ,''))
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.RESET_COUNTER,''))
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.RESUME_READING,''))   
        if(self.theReader is not None):         
            if(self.theReader.is_alive()):
                return
        self.theReader = Process(target=self.ReadWorker)                 
        self.theReader.start()
        self.QueueMessage("Reader started.")      
        
    def ReadValues(self, currentReadIndex): 
        currentTime = datetime.datetime.today()        
        for info in self.DFMInfos:
            try:
                tmp=self.theCOMM.GetStatusPacket(info.ID,info.DFMType)                                    
                self.ProcessPacket(info,tmp,currentTime,currentReadIndex)
                packList=[self.currentStatusPacket]                   
                self.data_q.put(packList)                       
            except:                
                ss = "Get status exception " + str(id) +"."
                self.QueueMessage(ss)
            time.sleep(0.002)        

    def QueueMessage(self,message):
        if(self.verbose and self.message_q.qsize()<1000):
            self.message_q.put(MP_Message(message))

    def QueueCommand(self,command):        
        self.command_q.put(command)
        if(self.verbose):
            ss = "Command queued (" + str(command.arguments[0])+"): " +str(command.commandType)
            self.QueueMessage(ss)

    def ReadWorker(self):
        currentReadIndex=1
        continueRunning=True  
        isPaused=False      
        self.QueueMessage("Read worker started.")        
        lastTime = time.time()   
        while(continueRunning):
            try:
                tmp=self.command_q.get(False)
                if(tmp.commandType==Enums.COMMANDTYPE.STOP_READING):
                    continueRunning = False
                elif(tmp.commandType==Enums.COMMANDTYPE.PAUSE_READING):
                    isPaused=True
                elif(tmp.commandType==Enums.COMMANDTYPE.RESUME_READING):
                    isPaused=False
                elif(tmp.commandType==Enums.COMMANDTYPE.RESET_COUNTER):
                    currentReadIndex=1
                elif(tmp.commandType==Enums.COMMANDTYPE.CLEARALLQ):
                    self.ClearQueuesInternal()                    
                elif(tmp.commandType==Enums.COMMANDTYPE.SET_VERBOSE):
                    self.verbose=True
                elif(tmp.commandType==Enums.COMMANDTYPE.CLEAR_VERBOSE):
                    self.verbose=False
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_DARK):                   
                    # Dark arguments 1=ID, 2=Dark state
                    self.theCOMM.SendDark(tmp.arguments[0],tmp.arguments[1])
                    ss = "Dark state sent to DFM " + str(tmp.arguments[0]) +"."                    
                    self.QueueMessage(ss) 
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.   
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_FREQ):                                       
                    self.theCOMM.SendFrequency(tmp.arguments[0],tmp.arguments[1])  
                    ss = "Freqeuncy sent to DFM " + str(tmp.arguments[0]) +"."                   
                    self.QueueMessage(ss)     
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.      
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_PW):                                                           
                    self.theCOMM.SendPulseWidth(tmp.arguments[0],tmp.arguments[1])  
                    ss = "Pulsewidth sent to DFM " + str(tmp.arguments[0]) +"."                    
                    self.QueueMessage(ss)     
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.     
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_OPTOSTATE):                   
                    # Dark arguments 1=ID, 2=Dark state                    
                    self.theCOMM.SendOptoState(tmp.arguments[0],tmp.arguments[1],tmp.arguments[2])  
                    ss = "Optostate sent to DFM " + str(tmp.arguments[0]) +"."                    
                    self.QueueMessage(ss)    
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.       
            except:
                if(isPaused==False):
                    if(time.time()-lastTime>.2):                                                               
                        lastTime = time.time() 
                        self.ReadValues(currentReadIndex)   
                        currentReadIndex+=1                                                                                 
            time.sleep(0.002)
            # Note that when reading is stopped it should stop (especially for V3)
            # after the last DFM in the list, not in the middle somehwere.
        self.QueueMessage("Read worker ended.")                
        return


    def ProcessPacket(self,info,bytesData,currentTime,currentReadIndex):         
        if(len(bytesData)==0):        
            self.currentStatusPacket=StatusPacket.StatusPacket(0,0,info.DFMType)
            self.currentStatusPacket.processResult = Enums.PROCESSEDPACKETRESULT.NOANSWER
            return  
            
        tmpPacket = StatusPacket.StatusPacket(currentReadIndex,info.ID,info.DFMType)
        tmpPacket.ProcessStatusPacket(bytesData,currentTime)          
        self.currentStatusPacket = tmpPacket        
        return 


if __name__=="__main__" :
    Board.BoardSetup()   
    mp=DataGetterI2C()

    mp.FindDFM()
    time.sleep(0.2)
    counter=0

    while counter<200000:
        tmp = mp.data_q.get(block=True)        
        counter+=1
        if(counter % 2000 ==0):
            print(counter)

    mp.StopReading()

    while mp.isRunning==True:
        pass
        
    time.sleep(1)
    while mp.message_q.empty() != True:
        tmp = mp.message_q.get()
        print(tmp.message)

        