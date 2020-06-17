import OptoWell

class OptoLid:
    def __init__(self):
        self.theWells = []
        self.optoStateCol1=0
        self.optoStateCol2=0
        for i in range(0,12):
            self.theWells.append(OptoWell.OptoWell())

    def UpdateWithInstruction(self, currentInstruction):
        self.SetAllThresholds(currentInstruction.adjustedThresholds)    
        for i in range(0,12):
            self.theWells[i].delay=currentInstruction.delay
            self.theWells[i].decay=currentInstruction.decay            
            self.theWells[i].maxTimeOn = currentInstruction.maxTimeOn

    def SetThreshold(self, thresh, well):
        if(well<0 or well>11):
            return
        self.theWells[well]=thresh

    def SetAllThresholds(self,thresh):
        if(len(thresh)!=12):
            return
        for i in range(0,12):
            self.theWells[i].signalThreshold=thresh[i]

    def SetOptoState(self,currentSignals):
        for i in range(0,12):
            self.theWells[i].ProcessSignal(currentSignals[i])
        self.optoStateCol1=0
        self.optoStateCol2=0
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