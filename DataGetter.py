from multiprocessing import Queue, Process
import queue
import COMM
import datetime
import StatusPacket
import Enums
import math
import Board
import time


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
        self.isRunning = False   
        self.terminationRequest = False      
        self.counter=0
        self.theCOMM = COMM.I2CCOMM()
        self.DFMInfos = []        
        self.currentReadIndex=0

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
        self.message_q.put(MP_Message("Reader termination requested."))        
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.STOP_READING,''))
        if(block):
            while self.isRunning==True:
                pass

    def ClearQueues(self):
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
        
    def StartReading(self):
        self.currentReadIndex=0            
        self.ClearQueues()
        if(self.isRunning):
            return
        self.theReader = Process(target=self.ReadWorker)                 
        self.theReader.start()
        self.message_q.put(MP_Message("Reader started."))        
        
    def ReadValues(self): 
        currentTime = datetime.datetime.today()        
        for info in self.DFMInfos:
            try:
                tmp=self.theCOMM.GetStatusPacket(info.ID,info.DFMType)                                    
                self.ProcessPacket(info,tmp,currentTime)
                packList=[self.currentStatusPacket]                              
                self.data_q.put(packList)               
            except:
                ss = "Get status exception " + str(id) +"."
                self.message_q.put(MP_Message(ss)) 
            time.sleep(0.002)
        self.currentReadIndex+=1

    def SetDark(self,id,darkstate):
        args=[id,darkstate]
        if(darkstate==1):
            ss = "Dark state active request to DFM " + str(id) +"queued."
        else:
            ss = "Dark state inactive request to DFM " + str(id) +"queued."
        self.message_q.put(MP_Message(ss))        
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.SEND_DARK,args))

    def ReadWorker(self):
        continueRunning=True
        self.isRunning=True
        self.counter=0
        self.message_q.put(MP_Message("Read worker started."))
        lastTime = time.time()   
        while(continueRunning):
            try:
                tmp=self.command_q.get(False)
                if(tmp.commandType==Enums.COMMANDTYPE.STOP_READING):
                    continueRunning = False
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_DARK):                   
                    # Dark arguments 1=ID, 2=Dark state
                    self.theCOMM.SendDark(tmp.arguments[0],tmp.arguments[1])
                    ss = "Dark state sent to DFM " + str(id) +"."
                    self.message_q.put(MP_Message(ss)) 
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.   
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_FREQ):                   
                    # Dark arguments 1=ID, 2=Dark state
                    self.theCOMM.SendFrequency(tmp.arguments[0],tmp.arguments[1])  
                    ss = "Freqeuncy sent to DFM " + str(id) +"."
                    self.message_q.put(MP_Message(ss))     
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.      
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_PW):                   
                    # Dark arguments 1=ID, 2=Dark state
                    self.theCOMM.SendPulseWidth(tmp.arguments[0],tmp.arguments[1])  
                    ss = "Pulsewidth sent to DFM " + str(id) +"."
                    self.message_q.put(MP_Message(ss))     
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.     
                elif(tmp.commandType==Enums.COMMANDTYPE.SEND_OPTOSTATE):                   
                    # Dark arguments 1=ID, 2=Dark state
                    self.theCOMM.SendOptoState(tmp.arguments[0],tmp.arguments[1],tmp.arguments[2])  
                    ss = "Optostate sent to DFM " + str(id) +"."
                    self.message_q.put(MP_Message(ss))     
                    # Maybe think about putting a failed command back in the queue.
                    # For V2 command failure is not detected.       
            except:
                if(time.time()-lastTime>.2):                                                               
                    lastTime = time.time() 
                    self.ReadValues()                                                                        
            time.sleep(0.005)
            # Note that when reading is stopped it should stop (especially for V3)
            # after the last DFM in the list, not in the middle somehwere.
        self.message_q.put(MP_Message("Read worker ended."))
        self.isRunning=False
        return


    def ProcessPacket(self,info,bytesData,currentTime):         
        if(len(bytesData)==0):        
            self.currentStatusPacket=StatusPacket.StatusPacket(0,0,info.DFMType)
            self.currentStatusPacket.processResult = Enums.PROCESSEDPACKETRESULT.NOANSWER
            return  
            
        tmpPacket = StatusPacket.StatusPacket(self.currentReadIndex,info.ID,info.DFMType)
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

        