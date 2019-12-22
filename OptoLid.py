import Enums
import OptoWell

class OptoLid:
    def __init__(self,OLType):        
        self.lidType=OLType
        self.optoType = Enums.OPTOTYPE.ADAPTIVE
        self.theWells=[]
        for _ in range(0,12):
            self.theWells.append(OptoWell.OptoWell())
        self.optoStateCol1=0x00
        self.optoStateCol2=0x00

    def SetWellThreshold(self, wellnum, thresh):
        if(wellnum<0 or wellnum>11): return
        self.theWells[wellnum].signalThreshold=thresh

    def SetAllThresholds(self,thresholds):
        if(len(thresholds)!=12): return
        for i in range(0,12):
            self.theWells[i].signalThreshold=thresholds[i]
        
    def SetOptoState(self,currentSignals):
        if(self.optoType==Enums.OPTOTYPE.ALLON):
            self.optoStateCol1=0x3F
            self.optoStateCol2=0x3F
        elif(self.optoType==Enums.OPTOTYPE.ADAPTIVE):          
            for i in range(0,12):
                self.theWells[i].ProcessSignal(currentSignals[i])
            if(self.lidType==Enums.OPTOLIDTYPE.ONECHAMBER):
                self.SetOptoState1Well()
            elif(self.lidType==Enums.OPTOLIDTYPE.SIXCHAMBER):
                self.SetOptoState6Well()
            elif(self.lidType==Enums.OPTOLIDTYPE.TWELVECHAMBER):
                self.SetOptoState12Well()
            else:
                self.optoStateCol1=0x00
                self.optoStateCol2=0x00    
        else:
            self.optoStateCol1=0x00
            self.optoStateCol2=0x00
    
    def SetOptoState12Well(self):
        self.optoStateCol1=0x00
        self.optoStateCol2=0x00
        if(self.theWells[0].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x01
        if(self.theWells[2].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x02
        if(self.theWells[4].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x04
        if(self.theWells[6].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x08
        if(self.theWells[8].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x10
        if(self.theWells[10].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x20

        if(self.theWells[1].isLEDOn):
            self.optoStateCol2 = self.optoStateCol2 | 0x01
        if(self.theWells[3].isLEDOn):
            self.optoStateCol2 = self.optoStateCol2 | 0x02
        if(self.theWells[5].isLEDOn):
            self.optoStateCol2 = self.optoStateCol2 | 0x04
        if(self.theWells[7].isLEDOn):
            self.optoStateCol2 = self.optoStateCol2 | 0x08
        if(self.theWells[9].isLEDOn):
            self.optoStateCol2 = self.optoStateCol2 | 0x10
        if(self.theWells[11].isLEDOn):
            self.optoStateCol2 = self.optoStateCol2 | 0x20

    def SetOptoState6Well(self):
        self.optoStateCol1=0x00
        self.optoStateCol2=0x00
        if(self.theWells[0].isLEDOn or self.theWells[1].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x01
            self.optoStateCol2 = self.optoStateCol2 | 0x01
        if(self.theWells[2].isLEDOn or self.theWells[3].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x02
            self.optoStateCol2 = self.optoStateCol2 | 0x02
        if(self.theWells[4].isLEDOn or self.theWells[5].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x04
            self.optoStateCol2 = self.optoStateCol2 | 0x04
        if(self.theWells[6].isLEDOn or self.theWells[7].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x08
            self.optoStateCol2 = self.optoStateCol2 | 0x08
        if(self.theWells[8].isLEDOn or self.theWells[9].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x10
            self.optoStateCol2 = self.optoStateCol2 | 0x10
        if(self.theWells[10].isLEDOn or self.theWells[11].isLEDOn):
            self.optoStateCol1 = self.optoStateCol1 | 0x20
            self.optoStateCol2 = self.optoStateCol2 | 0x20
    
    def SetOptoState1Well(self):
        self.optoStateCol1=0x00
        self.optoStateCol2=0x00
        for w in self.theWells:
            if(w.isLEDOn):
                self.optoStateCol1=0x3F
                self.optoStateCol2=0x3F
                return
