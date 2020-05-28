import multiprocessing
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

class DataGetterI2C:
    def __init__(self):
        #COMM.COMM.COMM_message+=self.NewMessageDirect
        self.data_q=multiprocessing.Queue()
        self.message_q=multiprocessing.Queue()
        self.command_q=multiprocessing.Queue()       
        self.currentStatusPacket = StatusPacket.StatusPacket(0,0)
        self.isRunning = False   
        self.terminationRequest = False      
        self.counter=0
        self.theCOMM = COMM.I2CCOMM()
        self.DFMIDs = []
        self.currentReadIndex=0

    def FindDFM(self, maxNum):      
        self.DFMIDs.clear()
        for i in range(1,maxNum+1):
            tmp = self.theCOMM.PollSlave(i)
            if(tmp != '' ):               
                self.DFMIDs.append(tmp)              
            time.sleep(0.1)
        if(len(self.DFMIDs) > 0):
            self.theReader = multiprocessing.Process(target=self.ReadWorker)      
            self.currentReadIndex=0               
            self.theReader.start()
        return self.DFMIDs

    def StopReading(self,block=True):        
        self.message_q.put(MP_Message("Reader termination requested."))        
        self.command_q.put(MP_Command(Enums.COMMANDTYPE.STOP_READING,''))
        if(block):
            while self.isRunning==True:
                pass


    def ReadValues(self): 
        currentTime = datetime.datetime.today()
        for id in self.DFMIDs:
            tmp=self.theCOMM.GetStatusPacket(id)                                    
            self.ProcessPacket(id,tmp,currentTime)
            #print(self.currentStatusPackets[-1].GetConsolePrintPacket())    
            packList=[self.currentStatusPacket]                              
            self.data_q.put(packList)               
            time.sleep(0.002)
        self.currentReadIndex+=1

    def SetDark(self,id,darkstate):
        args=[id,darkstate]
        if(darkstate==1):
            ss = "Dark state active request to DFM " + str(id)
        else:
            ss = "Dark state inactive request to DFM " + str(id)
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
                    if(self.theCOMM.SetDark(tmp.arguments[0],tmp.arguments[1])==False):
                        self.message_q.put(MP_Message("Error sending dark state."))                
            except:
                if(time.time()-lastTime>.2):                                                               
                    lastTime = time.time() 
                    self.ReadValues()                                                                            
            time.sleep(0.005)

        self.message_q.put(MP_Message("Read worker ended."))
        self.isRunning=False
        return


    def ProcessPacket(self,id,bytesData,currentTime):         
        if(len(bytesData)==0):        
            self.currentStatusPacket=StatusPacket.StatusPacket(0,0)
            self.currentStatusPacket.processResult = Enums.PROCESSEDPACKETRESULT.NOANSWER
            return  
            
        tmpPacket = StatusPacket.StatusPacket(self.currentReadIndex,id)
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

        