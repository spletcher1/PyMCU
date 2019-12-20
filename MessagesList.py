import Message
import Enums
import Event


class MessageList():
    def __init__(self):
        self.theMessages = []
        self.OnMessageRaised=Event.Event()
    def __len__(self):
        return len(self.theMessages)
    def GetErrorCount(self):
        errors=0
        for m in self.theMessages:
            if(m.messageType==Enums.MESSAGETYPE.ERROR):
                errors+=1
        return errors    
    def GetMessageStringForFile(self):
        if(len(self.theMessages)==0):
            return "No messages\n"
        else:
            s="DFM,Date,Time,Millisecond,Sample,Message,MsgType\n"
            for i in self.theMessages:
                s+=i.GetMessageStringForFile()
        return s        
    def AddMessage(self,newmessage):
        self.theMessages.append(newmessage)
    def ClearMessages(self):
        self.theMessages.clear()

    def MessageRaised(self): 
        # This function will be executed once a lock is broken and will  
        # raise an event 
        self.OnMessageRaised() 
          
    def AddMessageSubscriber(self,objMethod): 
        self.OnMessageRaised += objMethod 
          
    def RemoveMessageSubscriber(self,objMethod): 
        self.OnMessageRaised -= objMethod 
