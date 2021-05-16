import platform
import Event
if("MCU" in platform.node()):
    import RPi.GPIO as GPIO


class BoardSetup():
    Camera_message = Event.Event()
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        self.ledPIN=13
        self.relayPIN=6
        self.boardIDPin=5
        self.cameraPin = 27

        GPIO.setup(self.ledPIN,GPIO.OUT)
        GPIO.setup(self.relayPIN,GPIO.OUT)
        #GPIO.setup(self.cameraPin,GPIO.IN,pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.cameraPin,GPIO.IN,pull_up_down=GPIO.PUD_DOWN)
        GPIO.output(self.relayPIN,GPIO.HIGH)
        GPIO.output(self.ledPIN,GPIO.HIGH) 
    
        GPIO.add_event_detect(self.cameraPin,GPIO.BOTH, callback=self.CameraSignalChanged)        

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


    def GetCameraState(self):
        return GPIO.input(self.cameraPin)==GPIO.HIGH

    def CameraSignalChanged(self, channel):        
        if(GPIO.input(self.cameraPin)==GPIO.LOW):
            BoardSetup.Camera_message.notify(False)  
        else:
            BoardSetup.Camera_message.notify(True)  

if __name__=="__main__" :
    tmp = BoardSetup()
    print(tmp.GetBoardVersion())