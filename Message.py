import Enums

class Message():
    def __init__(self,id,time,sample,mess,mt,number):
        self.DFMId =id
        self.timeOfError=time
        self.sample=sample
        self.message=mess
        self.messageType = mt
        self.messageNumber=number
    
    def __str__(self):
        ss="(" + str(self.messageNumber)+")"+self.timeOfError.strftime("%m/%d/%Y %H:%M:%S")
        ss+=" -> "+str(self.DFMId)+" <- "+self.message
        return ss

    def GetMessageStringForFile(self):        
      
        ms=str(self.DFMId)+"," +self.timeOfError.strftime("%m/%d/%Y,%H:%M:%S")+","
        millisec = self.timeOfError.microsecond /1000
        ms+=str(millisec)+","+str(self.sample)+","+self.message+","

        if(self.messageType==Enums.MESSAGETYPE.ERROR):
            ms+="Error\n"
        elif(self.messageType==Enums.MESSAGETYPE.NOTICE):
            ms+="Notice\n"
        elif(self.messageType==Enums.MESSAGETYPE.WARNING):
            ms+="Warning\n"
        else:
            ms+="Unknown\n"
        return ms
 
    def GetHeaderString(self):
        return "DFM,Date,Time,Millisecond,Sample,Message,MsgType\n"