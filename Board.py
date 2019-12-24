import platform
if(platform.node()=="raspberrypi"):
    import RPi.GPIO as GPIO


class BoardSetup():
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

        ledPIN=13
        relayPIN=6

        GPIO.setup(ledPIN,GPIO.OUT)
        GPIO.setup(relayPIN,GPIO.OUT)
        GPIO.output(relayPIN,GPIO.HIGH)
        GPIO.output(ledPIN,GPIO.HIGH) 
