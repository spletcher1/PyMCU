import platform
if("MCU" in platform.node()):
    import RPi.GPIO as GPIO


class BoardSetup():
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        self.ledPIN=13
        self.relayPIN=6
        self.boardIDPin=5

        GPIO.setup(self.ledPIN,GPIO.OUT)
        GPIO.setup(self.relayPIN,GPIO.OUT)
        GPIO.output(self.relayPIN,GPIO.HIGH)
        GPIO.output(self.ledPIN,GPIO.HIGH) 
    
        GPIO.setup(self.boardIDPin,GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

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
        if(GPIO.input(self.boardIDPin)):
            return "V3"
        else:
            return "V2"



    def TurnOffDFMPower(self):
        GPIO.output(self.relayPIN,GPIO.LOW)
        GPIO.output(self.ledPIN,GPIO.LOW)


if __name__=="__main__" :
    tmp = BoardSetup()
    print(tmp.GetBoardVersion())