import csv
import datetime
import io

import Enums

# Errors and annotations are always kept. Notices and warnings stop at this many, and the file
# says how many more there were.
MAX_NOTICES = 5000
# A message that comes again (same DFM, type and text) within this many seconds of the first of
# its kind is counted on that one rather than added again. A DFM that stops answering then costs
# one line per 10 minutes instead of one per read.
GROUP_SECONDS = 600
# What the screen shows; the file has everything.
SCREEN_TYPES = (Enums.MESSAGETYPE.ERROR, Enums.MESSAGETYPE.ANNOTATION)
FILE_HEADER = ["DFM","Date","Time","Millisecond","Sample","Message","MsgType"]


class MessageList():
    def __init__(self):
        self.theMessages = []
        self.maxNotices=MAX_NOTICES
        self.maxMessagesForScreen=100
        # Goes up with every change, so the file is rewritten only when there is something new.
        self.changeCount=0
        self.ClearMessages()
    def __len__(self):
        return len(self.theMessages)
    def __str__(self):
        shown = [m for m in self.theMessages if m.messageType in SCREEN_TYPES]
        if(not shown):
            return "No messages"
        ss = ""
        if(len(shown)>self.maxMessagesForScreen):
            ss = "The {} most recent of {} messages. All are in Messages.csv.\n".format(self.maxMessagesForScreen,len(shown))
            shown = shown[-self.maxMessagesForScreen:]
        return ss + "".join(str(m)+"\n" for m in shown)

    def GetErrorCount(self):
        return sum(1+m.repeatCount for m in self.theMessages if m.messageType==Enums.MESSAGETYPE.ERROR)

    def GetMessageStringForFile(self):
        if(len(self.theMessages)==0):
            return "No messages\n"
        # The csv module quotes any message with a comma, so it can't spill into the next column.
        f = io.StringIO()
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(FILE_HEADER)
        for m in self.theMessages:
            writer.writerow(m.FileRow())
        if(self.droppedNotices):
            now = datetime.datetime.today()
            writer.writerow([0,now.strftime("%m/%d/%Y"),now.strftime("%H:%M:%S"),now.microsecond/1000,0,
                             "{} more notices were not kept, after the first {}".format(self.droppedNotices,self.maxNotices),"Notice"])
        return f.getvalue()

    def AddMessage(self,newmessage):
        """Adds a message, or counts it on an earlier one like it. Returns False if it was dropped
        (a notice past the limit)."""
        key = (newmessage.DFMId, newmessage.messageType, newmessage.message)
        first = self.groups.get(key)
        if(first is not None and abs((newmessage.timeOfError-first.timeOfError).total_seconds()) < GROUP_SECONDS):
            first.repeatCount += 1
            first.lastTime = newmessage.timeOfError
            self.changeCount+=1
            return True
        isKept = newmessage.messageType in SCREEN_TYPES
        if(not isKept and self.noticeCount>=self.maxNotices):
            self.droppedNotices += 1
            return False
        if(not isKept):
            self.noticeCount += 1
        newmessage.messageNumber = len(self.theMessages)+1
        self.theMessages.append(newmessage)
        self.groups[key] = newmessage
        self.changeCount+=1
        return True

    def ClearMessages(self):
        self.theMessages.clear()
        # The latest message of each kind, which repeats are counted on.
        self.groups = {}
        self.noticeCount = 0
        self.droppedNotices = 0
        self.changeCount+=1
