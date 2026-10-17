import Enums

# Message types that have a label; anything else (e.g. annotations) is labelled "Unknown".
TYPE_LABELS = {
    Enums.MESSAGETYPE.ERROR: "Error",
    Enums.MESSAGETYPE.NOTICE: "Notice",
    Enums.MESSAGETYPE.WARNING: "Warning",
}

class Message():
    def __init__(self,id,time,sample,mess,mt,number):
        self.DFMId =id
        self.timeOfError=time
        self.sample=sample
        self.message=mess
        self.messageType = mt
        self.messageNumber=number
        # Further times the same message came soon after (see MessagesList), and the last of them.
        self.repeatCount=0
        self.lastTime=None

    def _TypeLabel(self):
        return TYPE_LABELS.get(self.messageType,"Unknown")

    def Text(self):
        """The message, with how often it repeated."""
        if(self.repeatCount==0):
            return self.message
        return "{} (repeated {} more time{}, the last at {})".format(
            self.message,self.repeatCount,"" if self.repeatCount==1 else "s",self.lastTime.strftime("%H:%M:%S"))

    def __str__(self):
        ss="(" + str(self.messageNumber)+")  "+self.timeOfError.strftime("%m/%d/%Y %H:%M:%S ")
        ss+="-> "+str(self.DFMId)+" <- "+self.Text()
        return ss+" ("+self._TypeLabel()+")"

    def FileRow(self):
        """The fields of this message's row in Messages.csv."""
        millisec = self.timeOfError.microsecond /1000
        return [self.DFMId,self.timeOfError.strftime("%m/%d/%Y"),self.timeOfError.strftime("%H:%M:%S"),
                millisec,self.sample,self.Text(),self._TypeLabel()]
