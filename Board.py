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

        self.cameraPin = 27

        GPIO.setup(ledPIN,GPIO.OUT)
        GPIO.setup(relayPIN,GPIO.OUT)
        #GPIO.setup(self.cameraPin,GPIO.IN,pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.cameraPin,GPIO.IN)
        GPIO.output(relayPIN,GPIO.HIGH)
        GPIO.output(ledPIN,GPIO.HIGH) 
    
        GPIO.add_event_detect(self.cameraPin,GPIO.BOTH, callback=self.CameraSignalChanged)        

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
