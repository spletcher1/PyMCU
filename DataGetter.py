from multiprocessing import Queue, Process
import queue
import COMM
import datetime
import StatusPacket
from Enums import COMMTYPE,DFMTYPE,COMMANDTYPE,PROCESSEDPACKETRESULT,STATUSREQUESTTYPE
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
    def __str__(self):
        return str(self.ID) + str(self.DFMType)
    def __repr__(self):
        return "ID= "+ str(self.ID) + " Type= " + str(self.DFMType)


class DataGetter:
    def __init__(self):
        self.message_q=Queue()
        self.command_q=Queue()               
        self.answer_q=Queue()      
        self.data_q=Queue()   
        self.theCOMM = None                
        self.COMMType = None
        self.DFMInfos = []    
        self.focalDFMs = []            
        self.verbose=False
        self.theReader=None
        self.refreshRate=0.25
        self.startTime = datetime.datetime.today()
        self.currentReadIndex=1
        self.continueRunning = False
        self.isPaused = False
        self.theReader = Process(target=self.ReadWorker)
        self.theReader.start()
        self.QueueMessage("Reader started.")   
        self.getLatestStatusOnly=False   

    #region Functions that can be called from outside the process

    def StopReading(self):   
        self.QueueMessage("Reader termination requested.")         
        self.command_q.put(MP_Command(COMMANDTYPE.STOP_READING,''))              
    def GetAnswer(self, blk=True,tout=1):
        if(blk):
            try:                
                tmp = self.answer_q.get(block=True,timeout=tout)                              
                return tmp
            except:                
                return None
        else:
            try:
                tmp = self.answer_q.get(False)
                return tmp
            except:
                return None 
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
    def FindDFM(self,COMMType):
        self.command_q.put(MP_Command(COMMANDTYPE.FIND_DFM,[COMMType]))
        return self.GetAnswer(blk=True,tout=20)
    def SetReadInterval(self,interval):
        self.command_q.put(MP_Command(COMMANDTYPE.SET_REFRESHRATE,[interval]))
    def SetFocusDFM(self,dfmid):  
        self.command_q.put(MP_Command(COMMANDTYPE.SET_FOCAL_DFM,[dfmid]))    
    def SetStatusRequestType(self,requestType):
        if(requestType==STATUSREQUESTTYPE.LATESTONLY):
            self.command_q.put(MP_Command(COMMANDTYPE.SET_GET_LATESTSTATUS,''))
        else:
            self.command_q.put(MP_Command(COMMANDTYPE.SET_GET_NORMALSTATUS,''))


                    

  
    #endregion


    # Remember that any variables set at the time of process forking can not be changed except
    # Through a queue.
    def FindDFMInternal(self): 
        if(self.theCOMM is None):
            print("COMM not defined.")
            return []            
        self.DFMInfos.clear()
        for i in range(1,15+1):
            tmp = self.theCOMM.PollSlave(i)
            if(tmp != '' ):                
                self.DFMInfos.append(DFMInfo(i,tmp))                        
            time.sleep(0.010)
        if(len(self.DFMInfos) > 0):
            self.StartReading()
            self.isPaused=False        
        return self.DFMInfos

  
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
        try:
            while True:
                self.answer_q.get_nowait()
        except queue.Empty:
            pass        
        
    def ProcessCommand(self):
        try:
            tmp=self.command_q.get(False)  
        except:
            return False        
        if (tmp is not None):  
            #print(tmp.commandType)
            if(tmp.commandType == COMMANDTYPE.FIND_DFM):              
                if(tmp.arguments[0]==COMMTYPE.UART):                  
                    self.theCOMM=COMM.UARTCOMM()
                    self.COMMType = COMMTYPE.UART                    
                    self.refreshRate=0.3
                    tmp = self.FindDFMInternal()  
                    if(len(tmp)>0):
                        self.focalDFMs = [tmp[0]]
                    self.answer_q.put(tmp)
                elif(tmp.arguments[0]==COMMTYPE.I2C):
                    self.theCOMM=COMM.I2CCOMM()
                    self.COMMType = COMMTYPE.I2C
                    self.refreshRate=0.2 
                    tmp = self.FindDFMInternal()    
                    if(len(tmp)>0):
                        self.focalDFMs = tmp                     
                    self.answer_q.put(tmp)
                else:
                    self.answer_q.put([])           
            elif(tmp.commandType==COMMANDTYPE.STOP_READING):
                self.DFMInfos = []  
                self.theCOMM = None
                self.refreshRate=0.25
                self.isPaused=True
            elif(tmp.commandType==COMMANDTYPE.PAUSE_READING):                    
                self.isPaused=True
            elif(tmp.commandType==COMMANDTYPE.RESUME_READING):                    
                self.isPaused=False             
            elif(tmp.commandType==COMMANDTYPE.RESET_COUNTER):                    
                self.currentReadIndex=1                
            elif(tmp.commandType==COMMANDTYPE.CLEAR_DATAMESSQ):
                self.ClearQueuesInternal()                                        
            elif(tmp.commandType==COMMANDTYPE.SET_VERBOSE):
                self.verbose=True
            elif(tmp.commandType==COMMANDTYPE.CLEAR_VERBOSE):
                self.verbose=False   
            elif(tmp.commandType==COMMANDTYPE.SET_STARTTIME):
                self.startTime=tmp.arguments[0]                                 
            elif(tmp.commandType==COMMANDTYPE.SET_REFRESHRATE):
                self.refreshRate = tmp.arguments[0]                                          
            elif(tmp.commandType==COMMANDTYPE.BUFFER_RESET):                  
                answer=self.theCOMM.RequestBufferReset(tmp.arguments[0])                                    
                self.answer_q.put([tmp.arguments[0],answer])                
            elif(tmp.commandType==COMMANDTYPE.SET_FOCAL_DFM):
                if(tmp.arguments[0]==0):
                    self.focalDFMs = self.DFMInfos
                else:
                    for i in self.DFMInfos:                        
                        if i.ID == tmp.arguments[0]:
                            self.focalDFMs = [i]                                                        
            elif(tmp.commandType==COMMANDTYPE.LINKAGE):
                answer=self.theCOMM.SendLinkage(tmp.arguments[0],tmp.arguments[1])
                self.answer_q.put([tmp.arguments[0],answer])
            elif(tmp.commandType==COMMANDTYPE.INSTRUCTION):
                answer=self.theCOMM.SendInstruction(tmp.arguments[0],tmp.arguments[1])
                self.answer_q.put([tmp.arguments[0],answer])
            elif(tmp.commandType==COMMANDTYPE.SEND_DARK):                                       
                self.theCOMM.SendDark(tmp.arguments[0],tmp.arguments[1])
                ss = "Dark state sent to DFM " + str(tmp.arguments[0]) +"."                    
                self.QueueMessage(ss) 
            elif(tmp.commandType==COMMANDTYPE.SEND_FREQ):                                       
                self.theCOMM.SendFrequency(tmp.arguments[0],tmp.arguments[1])  
                ss = "Freqeuncy sent to DFM " + str(tmp.arguments[0]) +"."                   
                self.QueueMessage(ss)                         
            elif(tmp.commandType==COMMANDTYPE.SEND_PW):                                                           
                self.theCOMM.SendPulseWidth(tmp.arguments[0],tmp.arguments[1])  
                ss = "Pulsewidth sent to DFM " + str(tmp.arguments[0]) +"."                    
                self.QueueMessage(ss)                         
            elif(tmp.commandType==COMMANDTYPE.SEND_OPTOSTATE):                                       
                self.theCOMM.SendOptoState(tmp.arguments[0],tmp.arguments[1],tmp.arguments[2])  
                ss = "Optostate sent to DFM " + str(tmp.arguments[0]) +"."                                
                self.QueueMessage(ss)   
            elif(tmp.commandType==COMMANDTYPE.SET_GET_LATESTSTATUS):
                self.getLatestStatusOnly=True
            elif(tmp.commandType==COMMANDTYPE.SET_GET_NORMALSTATUS):
                self.getLatestStatusOnly=False
            else:
                print("Unknown Command")
                return False 
        else:
            return False
        return True

    def ReadWorker(self):
        self.currentReadIndex=1
        self.refreshRate=0.25
        self.isPaused=True      
        self.QueueMessage("Read worker started.")        
        lastTime = time.time()   
        while(True):  
            #if(self.ProcessCommand()==False):         
            self.ProcessCommand()
            if(self.isPaused==False):
                if(time.time()-lastTime>self.refreshRate):                                                               
                    lastTime = time.time() 
                    self.ReadValues()                                                                                                                                   
            time.sleep(0.001)
            # Note that when reading is stopped it should stop (especially for V3)
            # after the last DFM in the list, not in the middle somehwere.
        self.QueueMessage("Read worker ended.")                
        return
    
    def ReadValues(self): 
        currentTime = datetime.datetime.today()        
        for info in self.focalDFMs:
            try:
                bytesData=self.theCOMM.GetStatusPacket(info.ID,info.DFMType,self.getLatestStatusOnly)                                                                                                             
                packList=self.ProcessPacket(info,bytesData,currentTime)     
                tmp = True    
                for p in packList:
                    if p.processResult != PROCESSEDPACKETRESULT.OKAY:
                        tmp = False
                if (tmp):
                    self.theCOMM.SendAck(info.ID)                
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
            currentStatusPacket=StatusPacket.StatusPacket(0,info.ID,info.DFMType)            
            currentStatusPacket.processResult = PROCESSEDPACKETRESULT.NOANSWER                    
            return [currentStatusPacket]          
        if(info.DFMType==DFMTYPE.PLETCHERV3):           
            numPacketsReceived = len(bytesData)/66                                 
            if (math.floor(numPacketsReceived)!=numPacketsReceived):             
                currentStatusPacket=StatusPacket.StatusPacket(0,info.ID,info.DFMType)
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

def ModuleTest():
    Board.BoardSetup()
    mp=DataGetter()
    mp.theCOMM=COMM.UARTCOMM()
    mp.COMMType = COMMTYPE.UART  
    print(mp.FindDFMInternal())
    return
    mp.theCOMM.RequestBufferReset(6)
    time.sleep(1)

    for i in range(0,10):
        mp.ReadValues()
        print('*')        
        time.sleep(1)
    


if __name__=="__main__" :
    ModuleTest()
    