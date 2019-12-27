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
        self.theDFMGroup = DFMGroup.DFMGroup(COMM.TESTCOMM())          
        #self.theDFMGroup = DFMGroup.DFMGroup(COMM.UARTCOMM())
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

        self.main_widget = QtWidgets.QWidget(self)
        self.theDFMDataPlot = DFMPlot.MyDFMDataPlot(self.main_widget,backcolor=tmp,width=5, height=4, dpi=100)
        #dc = DFMPlot.MyDynamicMplCanvas(self.main_widget, width=5, height=4, dpi=100)
        self.DFMPlotLayout.addWidget(self.theDFMDataPlot)
        
        
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
            tmp.setFlat(True)
            tmp.setMinimumHeight(35)
            #tmp.setMaximumWidth(88)
            self.DFMListLayout2.setAlignment(Qt.AlignTop)
            self.DFMListLayout2.addWidget(tmp)            
            self.DFMButtons.append(tmp)
            self.SetActiveDFM(0)   
        self.StatusBar.showMessage(str(len(self.theDFMGroup.theDFMs)) + " DFMs found.",3000)                

        for b in self.DFMButtons:
            b.clicked.connect(self.DFMButtonClicked)     
        self.UpdateDFMPageGUI()
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
            self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))          
            if self.activeDFMNum>-1 and self.StackedPages.currentIndex()==1:
                self.UpdateDFMPageGUI()
                self.theDFMDataPlot.UpdateFigure(self.activeDFM)
                
            elif self.StackedPages.currentIndex()==2:
                self.UpdateMessagesGUI
            time.sleep(1)
                
    def closeEvent(self,event):
        self.stopUpdateLoop=True
        self.ClearDFM()

    # slot
    def browseSlot( self ):
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


