import Enums


class MessageList():
    def __init__(self):
        self.theMessages = []
        self.maxMessages=500
        self.maxMessagesForScreen=100
        # Goes up with every change, so the file is rewritten only when there is something new.
        self.changeCount=0
    def __len__(self):
        return len(self.theMessages)
    def __str__(self):
        ss="No messages"
        count=0
        for m in self.theMessages:
            if(m.messageType == Enums.MESSAGETYPE.ERROR or m.messageType == Enums.MESSAGETYPE.ANNOTATION):
                if(count==0):
                    ss=""
                ss+=str(m)+"\n"
                count+=1
                if(count>self.maxMessagesForScreen):
                    ss+="Max messages displayed. Check file for details."
                    break
        return ss

    def GetErrorCount(self):
        return sum(1 for m in self.theMessages if m.messageType==Enums.MESSAGETYPE.ERROR)

    def GetMessageStringForFile(self):
        if(len(self.theMessages)==0):
            return "No messages\n"
        s="DFM,Date,Time,Millisecond,Sample,Message,MsgType\n"
        for i in self.theMessages:
            s+=i.GetMessageStringForFile()
        return s

    def AddMessage(self,newmessage):
        newmessage.messageNumber = len(self.theMessages)+1
        if(len(self.theMessages)>self.maxMessages):
            return False
        if(len(self.theMessages)==self.maxMessages):
            # The last slot is used to say that the list is full.
            newmessage.DFMId = 0
            newmessage.messageType=Enums.MESSAGETYPE.NOTICE
            newmessage.message = "Reached max messages"
        self.theMessages.append(newmessage)
        self.changeCount+=1
        return True

    def ClearMessages(self):
        self.theMessages.clear()
        self.changeCount+=1
