import OptoWell

class OptoLid:
    def __init__(self):
        self.theWells = []
        self.optoStateCol1=0
        self.optoStateCol2=0
        self.linkRelations={}
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


    def SetLinkage(self,theLinkage):
        self.linkRelations={}
        for i in range(0,12):
            tmp = theLinkage[i]
            links=[]
            for j in range(0,12):
                if(j==i):
                    continue
                if(theLinkage[j]==tmp):                
                    links.append(j)
            self.linkRelations[i]=links

    def UpdateOptoWellsFromLinkage(self):
        for key,value in self.linkRelations.items():
            if(self.theWells[key].isLEDOn):
                for other in value:
                    self.theWells[other].isLEDOn=True


    def SetOptoState(self,currentSignals):
        for i in range(0,12):
            self.theWells[i].ProcessSignal(currentSignals[i])
        self.UpdateOptoWellsFromLinkage()
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