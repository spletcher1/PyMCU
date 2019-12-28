import sys
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import datetime
import time
import threading
import platform
import DFMGroup 
import COMM
import Enums
import Board
import DFMPlot
if(platform.node()=="raspberrypi"):
    import RPi.GPIO as GPIO


#class MyMainWindow(QMainWindow, Ui_MainWindow ):
class MyMainWindow(QtWidgets.QMainWindow):
    def __init__( self ):       
        super(MyMainWindow,self).__init__()        
        uic.loadUi("Mainwindow.ui",self)
        tmp = self.DFMErrorGroupBox.palette().color(QtGui.QPalette.Background).name()
        tmp2 = "QTextEdit {background-color: "+tmp+"}"
        self.MessagesTextEdit.setStyleSheet(tmp2)        
        self.ProgramTextEdit.setStyleSheet(tmp2)
        self.theDFMGroup = DFMGroup.DFMGroup(COMM.TESTCOMM())          
        #self.theDFMGroup = DFMGroup.DFMGroup(COMM.UARTCOMM())
        self.statusmessageduration=5000
        self.activeDFMNum=-1
        self.activeDFM=None                        
        self.MakeConnections()
        self.StackedPages.setCurrentIndex(1)
        self.statusLabel = QLabel()  
        self.statusLabel.setFrameStyle(QFrame.NoFrame)
        self.statusLabel.setFrameShadow(QFrame.Plain)
        self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))
        self.StatusBar.addPermanentWidget(self.statusLabel)        
        self.stopUpdateLoop=False
        self.guiThread = threading.Thread(target=self.UpdateGUI)
        self.guiThread.start()
        self.DFMButtons = []
        self.UpdateProgramGUI()

        self.main_widget = QtWidgets.QWidget(self)
        self.theDFMDataPlot = DFMPlot.MyDFMDataPlot(self.main_widget,backcolor=tmp,width=5, height=4, dpi=100)
        #dc = DFMPlot.MyDynamicMplCanvas(self.main_widget, width=5, height=4, dpi=100)
        self.DFMPlotLayout.addWidget(self.theDFMDataPlot)   

        self.programDuration = datetime.timedelta(minutes=180)
        self.SetProgramStartTime(datetime.datetime.today())

      
      
      

    def DisableButtons(self):
        self.findDFMAction.setEnabled(False)
        self.clearDFMAction.setEnabled(False)
        self.saveDataAction.setEnabled(False)
        self.clearMessagesAction.setEnabled(False)
        self.deleteDataAction.setEnabled(False)
        self.powerOffAction.setEnabled(False)
        self.T30MinButton.setEnabled(False)
        self.T60MinButton.setEnabled(False)
        self.T3HrButton.setEnabled(False)
        self.T6HrButton.setEnabled(False)
        self.T12HrButton.setEnabled(False)
        self.T24HrButton.setEnabled(False)
        self.T5DButton.setEnabled(False)
        self.CustomButton.setEnabled(False)
        self.StartTimeNowButton.setEnabled(False)
        self.StartTimeEdit.setEnabled(False)

    def EnableButtons(self):
        self.findDFMAction.setEnabled(True)
        self.clearDFMAction.setEnabled(True)
        self.saveDataAction.setEnabled(True)
        self.clearMessagesAction.setEnabled(True)
        self.deleteDataAction.setEnabled(True)
        self.powerOffAction.setEnabled(True)
        self.T30MinButton.setEnabled(True)
        self.T60MinButton.setEnabled(True)
        self.T3HrButton.setEnabled(True)
        self.T6HrButton.setEnabled(True)
        self.T12HrButton.setEnabled(True)
        self.T24HrButton.setEnabled(True)
        self.T5DButton.setEnabled(True)
        self.CustomButton.setEnabled(True)
        self.StartTimeNowButton.setEnabled(True)
        self.StartTimeEdit.setEnabled(True)

    def SetProgramStartTime(self,theTime):
        self.programStartTime = datetime.datetime.today() + datetime.timedelta(minutes=1)    
        self.programEndTime = self.programStartTime + self.programDuration        
        qtDate=QtCore.QDateTime.currentDateTime()    
        ss=self.programStartTime.strftime("%m-%d-%Y %H:%M:%S")        
        qtDate = QtCore.QDateTime.fromString(ss,"MM-dd-yyyy HH:mm:ss")        
        self.StartTimeEdit.setDateTime(qtDate)
        self.theDFMGroup.currentProgram.startTime = self.programStartTime
        self.StatusBar.showMessage("Set program start time: " + self.programStartTime.strftime("%m/%d/%Y %H:%M:%S") ,self.statusmessageduration)


    def SetSimpleProgramButtonClicked(self):
        if(len(self.theDFMGroup.theDFMs)==0): return
        sender = self.sender()
        tmp = sender.text()
        self.programStartTime = datetime.datetime.today() + datetime.timedelta(minutes=1)
        if(tmp == "30 minutes"):
            self.programDuration = datetime.timedelta(minutes=30)          
            self.LoadSimpleProgram()  
        elif(tmp == "60 minutes"):
            self.programDuration = datetime.timedelta(minutes=60)            
            self.LoadSimpleProgram()
        elif(tmp == "3 hours"):
            self.programDuration = datetime.timedelta(minutes=180)
            self.LoadSimpleProgram()
        elif(tmp == "6 hours"):
            self.programDuration = datetime.timedelta(minutes=60*6)
            self.LoadSimpleProgram()
        elif(tmp == "12 hours"):
            self.programDuration = datetime.timedelta(minutes=60*12)
            self.LoadSimpleProgram()
        elif(tmp == "24 hours"):
            self.programDuration = datetime.timedelta(minutes=60*24)
            self.LoadSimpleProgram()
        elif(tmp == "5 days"):
            self.programDuration = datetime.timedelta(minutes=60*24*5)
            self.LoadSimpleProgram()
        elif(tmp == "Custom"):
            self.LoadCustomProgram

        self.StatusBar.showMessage("Loaded simple program: " + tmp,self.statusmessageduration)
                            
    def ToggleProgramRun(self):
        if(len(self.theDFMGroup.theDFMs)==0): return
        if(self.theDFMGroup.currentProgram.isActive):
            self.RunProgramButton.setText("Run Program")
            self.theDFMGroup.StopCurrentProgram()
        else:
            self.RunProgramButton.setText("Stop Program")                         
            self.theDFMGroup.StageCurrentProgram()

    def LoadSimpleProgram(self):
        self.theDFMGroup.currentProgram.isProgramLoaded=False
        self.programEndTime = self.programStartTime + self.programDuration
        self.theDFMGroup.currentProgram.CreateSimpleProgram(self.programStartTime,self.programDuration)
        self.UpdateProgramGUI()
    
    def UpdateProgramGUI(self):
        if(len(self.theDFMGroup.theDFMs)>0):
            self.ProgramTextEdit.setText(self.theDFMGroup.currentProgram.GetProgramDescription())
        else:
            self.ProgramTextEdit.setText("No program loaded.")


    def setupUi( self, MW ):
        ''' Setup the UI of the super class, and add here code
        that relates to the way we want our UI to operate.
        '''
        super().setupUi( MW )

        # close the lower part of the splitter to hide the 
        # debug window under normal operations
        #self.splitter.setSizes([300, 0])
  
    def MakeConnections(self):                
        self.messagesAction.triggered.connect(self.GoToMessagesPage)
        self.findDFMAction.triggered.connect(self.FindDFMs)
        self.dataAction.triggered.connect(self.GotoDFMPage)
        self.programAction.triggered.connect(self.GoToProgramPage)
        self.clearDFMAction.triggered.connect(self.ClearDFM)
        self.clearMessagesAction.triggered.connect(self.ClearMessages)

        self.T30MinButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.T60MinButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.T3HrButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.T6HrButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.T12HrButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.T24HrButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.T5DButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.CustomButton.clicked.connect(self.SetSimpleProgramButtonClicked)
        self.RunProgramButton.clicked.connect(self.ToggleProgramRun)
        self.StartTimeNowButton.clicked.connect(self.SetStartTimeNow)

    def SetStartTimeNow(self):
        self.SetProgramStartTime(datetime.datetime.today())
        
        #self.programStartTime= tmp.toPyDateTime()
        

    def SetActiveDFM(self,num):
        self.activeDFMNum=num
        self.activeDFM = self.theDFMGroup.theDFMs[self.activeDFMNum]
        
        for i in range(0,len(self.DFMButtons)):
            if(i==self.activeDFMNum):
                self.DFMButtons[i].setStyleSheet('QPushButton {color: red}')
            else:
                self.DFMButtons[i].setStyleSheet('QPushButton {color: black}')

    def DFMButtonClicked(self):
        sender = self.sender()
        for i in range(0,len(self.DFMButtons)):
            if sender is self.DFMButtons[i]:
                self.SetActiveDFM(i)   
                self.UpdateDFMPageGUI()                    

    def FindDFMs(self):   
        self.StatusBar.showMessage("Searching for DFMs...")     
        self.ClearMessages()
        self.theDFMGroup.FindDFMs(2)
        self.DFMButtons=[]
        for d in self.theDFMGroup.theDFMs:
            s = str(d)
            tmp = QPushButton(s)
            tmp.setFlat(False)            
            tmp.setMinimumHeight(35)
            #tmp.setMaximumWidth(88)
            self.DFMListLayout2.setAlignment(Qt.AlignTop)
            self.DFMListLayout2.addWidget(tmp)            
            self.DFMButtons.append(tmp)
            self.SetActiveDFM(0)   
        self.StatusBar.showMessage(str(len(self.theDFMGroup.theDFMs)) + " DFMs found.",self.statusmessageduration)                

        for b in self.DFMButtons:
            b.clicked.connect(self.DFMButtonClicked)     
        self.UpdateDFMPageGUI()
        self.programStartTime = datetime.datetime.today()
        self.programDuration = datetime.timedelta(minutes=180)
        self.LoadSimpleProgram()
        self.GotoDFMPage()     
        
    def ClearMessages(self):
        self.theDFMGroup.theMessageList.ClearMessages()
        self.UpdateMessagesGUI()

    def ClearLayout(self,layout):
        while layout.count():
            child=layout.takeAt(0)
            if(child.widget()):
                child.widget().deleteLater()

    def ClearDFM(self):
        self.theDFMGroup.StopReading()
        self.ClearLayout(self.DFMListLayout2)
        self.activeDFMNum=-1
        self.activeDFM=None
        self.DFMButtons.clear()
        self.UpdateProgramGUI()
        self.ClearMessages()

    def GoToMessagesPage(self):
        self.StackedPages.setCurrentIndex(2)
        self.UpdateMessagesGUI()        

    def GoToProgramPage(self):        
        self.StackedPages.setCurrentIndex(0)
    
    def GotoDFMPage(self):
        self.StackedPages.setCurrentIndex(1)

    def UpdateMessagesGUI(self):
        self.MessagesTextEdit.setText(str(self.theDFMGroup.theMessageList))

    def UpdateDFMPageGUI(self):
        self.TempLabel.setText("{:.1f}C".format(self.activeDFM.reportedTemperature))
        self.HumidLabel.setText("{:.1f}%".format(self.activeDFM.reportedHumidity))
        self.LUXLabel.setText("{:d}".format(self.activeDFM.reportedLUX))
        self.VoltsInLabel.setText("{:.2f}V".format(self.activeDFM.reportedVoltsIn))
        if(self.activeDFM.reportedDarkState == Enums.DARKSTATE.ON):
            self.DarkModeLabel.setText("Yes")
        else:
            self.DarkModeLabel.setText("No")
        self.FrequencyLabel.setText("{:d}Hz".format(self.activeDFM.reportedOptoFrequency))
        self.PulseWidthLabel.setText("{:d}ms".format(self.activeDFM.reportedOptoPulsewidth))

        self.OptoStateLabel.setText("{:02X},{:02X}".format(self.activeDFM.reportedOptoStateCol1,self.activeDFM.reportedOptoStateCol2))

        if(self.activeDFM.status==Enums.CURRENTSTATUS.ERROR):
            self.CurrentStatusLabel.setText("Err")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.MISSING):
            self.CurrentStatusLabel.setText("Miss")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.READING):
            self.CurrentStatusLabel.setText("Read")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.RECORDING):
            self.CurrentStatusLabel.setText("Rec")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.UNDEFINED):
            self.CurrentStatusLabel.setText("None")

        if(self.activeDFM.pastStatus==Enums.PASTSTATUS.PASTERROR):
            self.PastStatusLabel.setText("Err")
        if(self.activeDFM.pastStatus==Enums.PASTSTATUS.ALLCLEAR):
            self.PastStatusLabel.setText("Clear")

        if(self.activeDFM.currentDFMErrors.GetI2CErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.I2CErrorBox.setChecked(False)
        else:
            self.I2CErrorBox.setChecked(False)

        if(self.activeDFM.currentDFMErrors.GetUARTErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.UARTErrorBox.setChecked(False)
        else:
            self.UARTErrorBox.setChecked(False)
         
        if(self.activeDFM.currentDFMErrors.GetPacketErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.PacketErrorBox.setChecked(False)
        else:
            self.PacketErrorBox.setChecked(False)
        if(self.activeDFM.currentDFMErrors.Getsi7021ErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.SIErrorBox.setChecked(False)
        else:
            self.SIErrorBox.setChecked(False)
        if(self.activeDFM.currentDFMErrors.GetTSL2591ErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.TSLErrorBox.setChecked(False)
        else:
            self.TSLErrorBox.setChecked(False)
        if(self.activeDFM.currentDFMErrors.GetConfigErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.ConfigErrorBox.setChecked(False)
        else:
            self.ConfigErrorBox.setChecked(False)
        if(self.activeDFM.currentDFMErrors.GetBufferErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.BufferErrorBox.setChecked(False)
        else:
            self.BufferErrorBox.setChecked(False)
        if(self.activeDFM.currentDFMErrors.GetMiscErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.MiscErrorBox.setChecked(False)
        else:
            self.MiscErrorBox.setChecked(False)

    def UpdateGUI(self):
        while True:
            if self.stopUpdateLoop:
                return           
            if (self.theDFMGroup.currentProgram.isActive):           
                self.theDFMGroup.UpdateProgramStatus()         
                self.DisableButtons()
            else:
                self.EnableButtons()
            self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))          
            if self.activeDFMNum>-1 and self.StackedPages.currentIndex()==1:
                self.UpdateDFMPageGUI()
                self.theDFMDataPlot.UpdateFigure(self.activeDFM,self.theDFMGroup.currentProgram.autoBaseline)                
            elif self.StackedPages.currentIndex()==2:
                self.UpdateMessagesGUI                          
            time.sleep(1)
                
    def closeEvent(self,event):
        self.stopUpdateLoop=True
        self.ClearDFM()

    # slot
    def LoadCustomProgram( self ):
        ''' Called when the user presses the Browse button
        '''
        #self.debugPrint( "Browse button pressed" )
        options = QtWidgets.QFileDialog.Options()
        options |= QtWidgets.QFileDialog.DontUseNativeDialog
        fileName, _ = QtWidgets.QFileDialog.getOpenFileName(
                        None,
                        "QFileDialog.getOpenFileName()",
                        "",
                        "All Files (*);;Python Files (*.py)",
                        options=options)

        ## Donr forget to set programstarttime and duration here 
        ## aFTER THE program is loaded.
        print(fileName)



def main():
    if(platform.node()=="raspberrypi"):
        Board.BoardSetup()  
    
    app = QtWidgets.QApplication(sys.argv)
    #app.setStyleSheet("QStatusBar.item {border : 0px black}")
    myapp = MyMainWindow()
    if(platform.node()=="raspberrypi"):
        myapp.showFullScreen()
    else:
        myapp.show()
       
    sys.exit(app.exec_())    
    print("Done")
    

    


if __name__ == "__main__":
    main()


