 import Message
 import Enums


 class MessageList():
    def __init__(self):
        self.theMessages = []
    def __len__(self):
        return len(self.theMessages)
    def GetErrorCount(self):
        errors=0
        for m in self.theMessages:
            if(m.messageType==Enums.MESSAGETYPE.ERROR):
                errors+=1
        return errors    
    def AddMessage(self,newmessage):
        self.theMessages.append(newmessage)
    def ClearMessages(self):
        self.theMessages.clear()
