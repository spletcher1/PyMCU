
class Experiment:    
    def __init__(self): 
        self.__startTime = datetime.datetime.today() 
        self.__endTime = datetime.datetime.today() 
        self.__isActive = False

    @property
    def IsActive(self):
        return self.__isActive

    @IsActive.setter
    def IsActive(self,val):
        if val==False or val==0:
            self.__isActive = False
        else :
            self.__isActive = True

    @property
    def StartTime(self):
        return self.__startTime

    @StartTime.setter
    def StartTime(self,val):
        self.__startTime = val

    @property
    def EndTime(self):
        return self.__endTime

    @EndTime.setter
    def EndTime(self,val):
        self.__endTime = val

    def IsDuringExperiment(self):
        t = datetime.datetime.today() 
        if(t> self.__startTime and t<self.__endTime):
            return True
        else :
            return False

    def IsBeforeExperiment(self):
        t = datetime.datetime.today() 
        if(t < self.__startTime):
            return True
        else :
            return False

    def IsAfterExperiment(self):
        t = datetime.datetime.today() 
        if(t > self.__endTime):
            return True
        else :
            return False


