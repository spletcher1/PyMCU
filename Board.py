import platform
if("MCU" in platform.node()):
    import RPi.GPIO as GPIO


class BoardSetup():
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        self.ledPIN=13
        self.relayPIN=6

        GPIO.setup(self.ledPIN,GPIO.OUT)
        GPIO.setup(self.relayPIN,GPIO.OUT)
        GPIO.output(self.relayPIN,GPIO.HIGH)
        GPIO.output(self.ledPIN,GPIO.HIGH) 
    
    def TurnOffDFMPower(self):
        GPIO.output(self.relayPIN,GPIO.LOW)
        GPIO.output(self.ledPIN,GPIO.LOW)
