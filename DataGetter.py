from multiprocessing import Queue, Process
import queue
import COMM
import datetime
import StatusPacket
from Enums import COMMTYPE,DFMTYPE,COMMANDTYPE
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

class DFMInfo:
    def __init__(self,id,dfmtype):
        self.ID = id
        self.DFMType=dfmtype


class DataGetter:
    def __init__(self,mctype):
        #COMM.COMM.COMM_message+=self.NewMessageDirect
        self.data_q=Queue()
        self.message_q=Queue()
        self.command_q=Queue()               
        if(mctype==COMMTYPE.I2C):                        
            self.theCOMM = COMM.I2CCOMM()
        else:
            self.theCOMM = COMM.UARTCOMM()
        self.COMMType = mctype
        self.DFMInfos = []                
        self.verbose=False
        self.theReader=None
        self.startTime = datetime.datetime.today()
        self.currentReadIndex=1

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
        self.command_q.put(MP_Command(COMMANDTYPE.STOP_READING,''))        
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
                self.data_q.get_nowait()
        except queue.Empty:
            pass        
        
    def ClearQueues(self):
        self.command_q.put(MP_Command(COMMANDTYPE.CLEAR_DATAMESSQ,''))
    def PauseReading(self):
        self.command_q.put(MP_Command(COMMANDTYPE.PAUSE_READING,''))
    def ResumeReading(self):
        self.command_q.put(MP_Command(COMMANDTYPE.RESUME_READING,''))
    def StartReading(self):        
        self.command_q.put(MP_Command(COMMANDTYPE.PAUSE_READING,''))
        self.command_q.put(MP_Command(COMMANDTYPE.CLEAR_DATAMESSQ,''))
        self.command_q.put(MP_Command(COMMANDTYPE.RESET_COUNTER,''))
        self.command_q.put(MP_Command(COMMANDTYPE.RESUME_READING,''))   
        if(self.theReader is not None):         
            if(self.theReader.is_alive()):
                return
        if(self.COMMType == COMMTYPE.I2C):    
            self.theReader = Process(target=self.ReadWorkerI2C)                 
        else:
            self.theReader = Process(target=self.ReadWorkerUART)                 
        self.theReader.start()
        self.QueueMessage("Reader started.")      

    def ReadWorkerUART(self):
        self.currentReadIndex=1
        refreshRate=0.25
        continueRunning=True  
        isPaused=False      
        self.QueueMessage("Read worker started.")        
        lastTime = time.time()   
        while(continueRunning):
            try:
                tmp=self.command_q.get(False)                
                if(tmp.commandType==COMMANDTYPE.STOP_READING):
                    continueRunning = False
                elif(tmp.commandType==COMMANDTYPE.PAUSE_READING):                    
                    isPaused=True
                elif(tmp.commandType==COMMANDTYPE.RESUME_READING):                    
                    isPaused=False             
                elif(tmp.commandType==COMMANDTYPE.RESET_COUNTER):                    
                    self.currentReadIndex=1                
                elif(tmp.commandType==COMMANDTYPE.CLEAR_DATAMESSQ):
                    self.ClearQueuesInternal()                                        
                elif(tmp.commandType==COMMANDTYPE.BUFFER_RESET):                  
                    self.theCOMM.RequestBufferReset(tmp.arguments[0])                    
                elif(tmp.commandType==COMMANDTYPE.SET_VERBOSE):
                    self.verbose=True
                elif(tmp.commandType==COMMANDTYPE.CLEAR_VERBOSE):
                    self.verbose=False   
                elif(tmp.commandType==COMMANDTYPE.SET_STARTTIME):
                    self.startTime=tmp.arguments[0]                                 
                elif(tmp.commandType==COMMANDTYPE.SET_REFRESHRATE):
                    refreshRate = tmp.arguments[0]                    
                elif(tmp.commandType==COMMANDTYPE.LINKAGE):
                    self.theCOMM.SendLinkage(tmp.arguments[0],tmp.arguments[1])
                elif(tmp.commandType==COMMANDTYPE.INSTRUCTION):
                    self.theCOMM.SendInstruction(tmp.arguments[0],tmp.arguments[1])
            except:
                if(isPaused==False):
                    if(time.time()-lastTime>refreshRate):                                                               
                        lastTime = time.time() 
                        self.ReadValues()                                                                                                     
            time.sleep(0.002)
            # Note that when reading is stopped it should stop (especially for V3)
            # after the last DFM in the list, not in the middle somehwere.
        self.QueueMessage("Read worker ended.")                
        return


    def ReadWorkerI2C(self):
        self.currentReadIndex=1
        continueRunning=True  
        isPaused=False      
        self.QueueMessage("Read worker started.")        
        lastTime = time.time()   
        while(continueRunning):
            try:
                tmp=self.command_q.get(False)
                if(tmp.commandType==COMMANDTYPE.STOP_READING):
                    continueRunning = False
                elif(tmp.commandType==COMMANDTYPE.PAUSE_READING):
                    isPaused=True
                elif(tmp.commandType==COMMANDTYPE.RESUME_READING):
                    isPaused=False
                elif(tmp.commandType==COMMANDTYPE.RESET_COUNTER):
                    self.currentReadIndex=1
                elif(tmp.commandType==COMMANDTYPE.CLEARALLQ):
                    self.ClearQueuesInternal()                    
                elif(tmp.commandType==COMMANDTYPE.SET_VERBOSE):
                    self.verbose=True
                elif(tmp.commandType==COMMANDTYPE.CLEAR_VERBOSE):
                    self.verbose=False
                elif(tmp.commandType==COMMANDTYPE.SEND_DARK):                   
                    # Dark arguments 1=ID, 2=Dark state
                    self.theCOMM.SendDark(tmp.arguments[0],tmp.arguments[1])
                    ss = "Dark state sent to DFM " + str(tmp.arguments[0]) +"."                    
                    self.QueueMessage(ss) 
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.   
                elif(tmp.commandType==COMMANDTYPE.SEND_FREQ):                                       
                    self.theCOMM.SendFrequency(tmp.arguments[0],tmp.arguments[1])  
                    ss = "Freqeuncy sent to DFM " + str(tmp.arguments[0]) +"."                   
                    self.QueueMessage(ss)     
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.      
                elif(tmp.commandType==COMMANDTYPE.SEND_PW):                                                           
                    self.theCOMM.SendPulseWidth(tmp.arguments[0],tmp.arguments[1])  
                    ss = "Pulsewidth sent to DFM " + str(tmp.arguments[0]) +"."                    
                    self.QueueMessage(ss)     
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.     
                elif(tmp.commandType==COMMANDTYPE.SEND_OPTOSTATE):                   
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
                        self.ReadValues()                                                                                                        
            time.sleep(0.002)
            # Note that when reading is stopped it should stop (especially for V3)
            # after the last DFM in the list, not in the middle somehwere.
        self.QueueMessage("Read worker ended.")                
        return
    
    def ReadValues(self): 
        currentTime = datetime.datetime.today()        
        for info in self.DFMInfos:
            try:
                bytesData=self.theCOMM.GetStatusPacket(info.ID,info.DFMType)                                    
                packList=self.ProcessPacket(info,bytesData,currentTime)
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

    def ProcessPacket(self,info,bytesData,currentTime):         
        if(len(bytesData)==0):        
            currentStatusPacket=StatusPacket.StatusPacket(0,0,info.DFMType)
            currentStatusPacket.processResult = PROCESSEDPACKETRESULT.NOANSWER
            return [currentStatusPacket] 
        if(info.DFMType==DFMTYPE.PLETCHERV3):           
            numPacketsReceived = len(bytesData)/66                                 
            if (math.floor(numPacketsReceived)!=numPacketsReceived):
                # TODO: Need to figure out how to possibly recover some of the packets.
                # TODO: for now, however, no.            
                currentStatusPacket=StatusPacket.StatusPacket(0,0,info.DFMType)
                currentStatusPacket.processResult = PROCESSEDPACKETRESULT.WRONGNUMBYTES
                return [currentStatusPacket]
            else:
                numPacketsReceived = int(numPacketsReceived)                                
            currentStatusPackets=[]
            for i in range(0,numPacketsReceived):               
                tmpPacket = StatusPacket.StatusPacket(self.currentReadIndex,info.ID,info.DFMType)  
                # This gets the startTime of the experiment.  The others get the time of the packet                                       
                tmpPacket.ProcessStatusPacket(bytesData,self.startTime,i)
                currentStatusPackets.append(tmpPacket)        
                self.currentReadIndex+=1        
            return currentStatusPackets
        else:
            currentStatusPacket = StatusPacket.StatusPacket(self.currentReadIndex,info.ID,info.DFMType)
            currentStatusPacket.ProcessStatusPacket(bytesData,currentTime)     
            self.currentReadIndex+=1                         
            return [currentStatusPacket]

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

        