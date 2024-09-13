import platform
import time
if("MCU" in platform.node()):
    from gpiozero import LED, InputDevice


class BoardSetup():
    def __init__(self):        

    

        self.output0pin=19
        self.output1pin=18
        self.ledPIN=13
        self.relayPIN=6
        self.boardIDPin=5

        self.Led = LED(self.ledPIN)
        self.relay = LED(self.relayPIN)
        self.BoardID = InputDevice(pin=self.boardIDPin, pull_up=False)
        
        self.TurnOnDFMPower()
        self.isPulsing=0

        GPIO.setup(self.ledPIN,GPIO.OUT)
        GPIO.setup(self.relayPIN,GPIO.OUT)
        GPIO.output(self.relayPIN,GPIO.HIGH)
        GPIO.output(self.ledPIN,GPIO.HIGH) 
    
        GPIO.setup(self.boardIDPin,GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        GPIO.setup(self.output0pin,GPIO.OUT)
        GPIO.setup(self.output1pin,GPIO.OUT)
        self.output0Frequency=40
        self.output0DC=32
        self.output1Frequency=40
        self.output1DC=32

        self.pwm0 = GPIO.PWM(self.output0pin,self.output0Frequency)        
        self.pwm1 = GPIO.PWM(self.output1pin,self.output1Frequency)
        

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

    def StartPulsing(self,lights):
        if(self.isPulsing==3):
            return
        if(lights==3):
            self.pwm0.start(self.output0DC)
            self.pwm1.start(self.output1DC)
            self.pwm0.ChangeFrequency(self.output0Frequency)
            self.pwm1.ChangeFrequency(self.output1Frequency)            
        elif(lights==2):
            self.pwm0.stop()            
            self.pwm1.start(self.output1DC)
            self.pwm1.ChangeFrequency(self.output1Frequency)
        elif(lights==1):
            self.pwm0.start(self.output0DC)
            self.pwm0.ChangeFrequency(self.output0Frequency)
            self.pwm1.stop()
        self.isPulsing=lights
        
    def TurnOnDFMPower(self):
        self.relay.on()
        self.Led.on()       

    def TurnOffDFMPower(self):
        self.relay.off()
        self.Led.off()        

if __name__=="__main__" :
    tmp = BoardSetup()
    print(tmp.GetBoardVersion())  
    time.sleep(10) 
