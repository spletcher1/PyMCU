import platform
import time
if("MCU" in platform.node()):
    from gpiozero import LED, InputDevice


class BoardSetup():
    def __init__(self):        

        self.ledPIN=13
        self.relayPIN=6
        self.boardIDPin=5

        self.Led = LED(self.ledPIN)
        self.relay = LED(self.relayPIN)
        self.BoardID = InputDevice(pin=self.boardIDPin, pull_up=False)
        

    def IsDFMV3Board(self):
        if (self.GetBoardVersion()=="V3"):
            return True
        else:
            return False
        
    def IsDFMV2Board(self):
        if (self.GetBoardVersion()=="V2"):
            return True
        else:
            return False
        
    def GetBoardVersion(self):
        if(self.BoardID.value):
            return "V3"
        else:
            return "V2"

    def TurnOnDFMPower(self):
        self.relay.on()
        self.Led.on()       

    def TurnOffDFMPower(self):
        self.relay.off()
        self.Led.off()        

if __name__=="__main__" :
    tmp = BoardSetup()
    print(tmp.GetBoardVersion())
    tmp.TurnOnDFMPower()   
    time.sleep(10) 
