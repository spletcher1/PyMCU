import platform
import Event
if("MCU" in platform.node()):
    import RPi.GPIO as GPIO


class BoardSetup():
    Camera_message = Event.Event()
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        ledPIN=13
        relayPIN=6

        self.cameraPin = 17

        GPIO.setup(ledPIN,GPIO.OUT)
        GPIO.setup(relayPIN,GPIO.OUT)
        GPIO.setup(self.cameraPin,GPIO.IN,pull_up_down=GPIO.PUD.UP)
        GPIO.output(relayPIN,GPIO.HIGH)
        GPIO.output(ledPIN,GPIO.HIGH) 

        GPIO.add_event_detect(self.cameraPin,GPIO.BOTH, callback=self.CameraSignalChanged)        

    def CameraSignalChanged(self, channel):
        print("Callback called! {:d}".format(channel))
        if(GPIO.input(self.cameraPin)==GPIO.LOW):
            BoardSetup.Camera_message.notify(False)  
        else:
            BoardSetup.Camera_message.notify(True)  
