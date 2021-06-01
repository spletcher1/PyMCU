import RPi.GPIO as GPIO
import time

class PIPulser:
    def __init__(self):
        self.output0Frequency=40
        self.output0DC=32

        self.output1Frequency=40
        self.output1DC=32        

        self.output0pin=19
        self.output1pin=18

        self.isPulsing=False
        
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.output0pin,GPIO.OUT)
        GPIO.setup(self.output1pin,GPIO.OUT)

        self.pwm0 = GPIO.PWM(self.output0pin,self.output0Frequency)        
        self.pwm1 = GPIO.PWM(self.output1pin,self.output1Frequency)
        
    def StartPulsing(self):
        if(self.isPulsing):
            return
        self.pwm0.start(self.output0DC)
        self.pwm1.start(self.output1DC)
        self.isPulsing=True

    def StopPulsing(self):
        if(not self.isPulsing):
            return
        self.pwm0.stop()
        self.pwm1.stop()
        self.isPulsing=False

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

    def UpdateStatus(self,freq0,dc0,freq1,dc1,pulsing):
        self.SetFrequency(freq0,0)
        self.SetFrequency(freq1,1)
        self.SetDC(dc0,0)
        self.SetDC(dc1,1)
        if(pulsing):
            self.StartPulsing()
        else:
            self.StopPulsing()



def ModuleTest():
    pp = PIPulser()
    pp.StartPulsing()
    print("Hellp")
    while(True):
        time.sleep(1000)
       
if __name__=="__main__":
    ModuleTest()
    print("Done!!")   