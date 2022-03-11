import Message
import Enums
import Event



class MessageList():
    def __init__(self):
        self.theMessages = []
        self.OnMessageRaised=Event.Event()
        self.maxMessages=500
        self.maxMessagesForScreen=100
    def __len__(self):
        return len(self.theMessages)
    def __str__(self):
        if(self.GetErrorCount()==0):
            return "No error messages"
        else:
            ss=""
            count=0
            for m in self.theMessages:
                if(m.messageType == Enums.MESSAGETYPE.ERROR):
                    ss+=str(m)+"\n"
                    count+=1
                    if(count>self.maxMessagesForScreen):
                        ss+="Max messages displayed. Check file for details."
                        break
            return ss


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
        newmessage.messageNumber = len(self.theMessages)+1
        if(len(self.theMessages)>self.maxMessages):
            return False
        if(len(self.theMessages)==self.maxMessages):
            newmessage.DFMID = 0
            newmessage.messageType=Enums.MESSAGETYPE.NOTICE
            newmessage.message = "Reached max messages"
            self.theMessages.append(newmessage)
        elif(len(self.theMessages)<self.maxMessages):
            self.theMessages.append(newmessage)
        else:
            pass
        return True
        
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
