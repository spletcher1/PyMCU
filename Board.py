import platform
if("MCU" in platform.node()):
    import RPi.GPIO as GPIO


class BoardSetup():
    def __init__(self):
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)

    

        self.output0pin=19
        self.output1pin=18
        self.ledPIN=13
        self.relayPIN=6
        self.boardIDPin=5

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
        if(GPIO.input(self.boardIDPin)):
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
        

    def StopPulsing(self):
        if(self.isPulsing==0):
            return
        self.pwm0.stop()
        self.pwm1.stop()
        self.isPulsing=0

    def SetFrequency(self, freq,output):
        if(output==0):
            self.output0Frequency=freq
            self.pwm0.ChangeFrequency(freq)
        elif(output==1):
            self.output1Frequency=freq
            self.pwm1.ChangeFrequency(freq)

    def SetDC(self,dc,output):
        if(output==0):
            self.pwm0.ChangeDutyCycle(dc)
            self.output0DC=dc
        elif(output==1):
            self.pwm1.ChangeDutyCycle(dc)
            self.output1DC=dc

    def UpdatePulsingStatus(self,freq0,dc0,freq1,dc1,pulsing):
        self.SetFrequency(freq0,0)
        self.SetFrequency(freq1,1)
        self.SetDC(dc0,0)
        self.SetDC(dc1,1)
        if(pulsing):
            self.StartPulsing()
        else:
            self.StopPulsing()

    def TurnOffDFMPower(self):
        GPIO.output(self.relayPIN,GPIO.LOW)
        GPIO.output(self.ledPIN,GPIO.LOW)


if __name__=="__main__" :
    tmp = BoardSetup()
    print(tmp.GetBoardVersion())