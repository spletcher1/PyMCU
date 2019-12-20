import DFMGroup
import MessagesList
import Message
import datetime
import Enums


class Event:
    def __init__(self):
        self.listeners = []

    def __iadd__(self, listener):
        """Shortcut for using += to add a listener."""
        self.listeners.append(listener)
        return self

    def notify(self, *args, **kwargs):
        for listener in self.listeners:
            listener(*args, **kwargs)

class MytmpAppMessage:
    def __init__(self):
        self.theMessageList = MessagesList.MessageList()
        self.theDFMs = []
        for i in range(1,5):
            t = MeTmpDFM(i)            
            self.theDFMs.append(t)
        MeTmpDFM.d_message+=self.NewMessage
            
        
    def NewMessage(self,tmp):        
        self.theMessageList.AddMessage(tmp)    

class MeTmpDFM:
    d_message = Event()
    
    def __init__(self,id):
        self.ID=id

    def NewMessage(self,ID, errorTime, sample,  message,mt):
        tmp = Message.Message(ID,errorTime,sample,message,mt,-99)
        MeTmpDFM.d_message.notify(tmp)

    def RaiseMessage(self):
        self.NewMessage(self.ID,datetime.datetime.today(),99,"Message!",Enums.MESSAGETYPE.ERROR)

def ModuleTest():
    tmp = MytmpAppMessage()
    tmp.theDFMs[0].RaiseMessage()
    tmp.theDFMs[1].RaiseMessage()
    print(tmp.theMessageList.GetMessageStringForFile())


if __name__=="__main__" :
    ModuleTest()   
    print("Done!!")     