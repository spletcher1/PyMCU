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
import socket
import os
import glob
if("MCU" in platform.node()):
    import RPi.GPIO as GPIO


class GUIUpdateThread(QtCore.QThread):
    updateGUISignal = QtCore.pyqtSignal()
    
    def __init__(self):
        QtCore.QThread.__init__(self)
        self.keepRunning=True
    def run(self):   
        while self.keepRunning:
            self.updateGUISignal.emit()
            time.sleep(1)
    def StopThread(self):
        self.keepRunning = False




#class MyMainWindow(QMainWindow, Ui_MainWindow ):
class MyMainWindow(QtWidgets.QMainWindow):
    def __init__( self ):       
        if("MCU" in platform.node()):
            self.theBoard=Board.BoardSetup()  
    
        super(MyMainWindow,self).__init__()        
        #uic.loadUi("/home/pi/Programming/Python/PyMCU/Mainwindow.ui",self)
        uic.loadUi("Mainwindow.ui",self)
        self.defaultBackgroundColor = self.DFMErrorGroupBox.palette().color(QtGui.QPalette.Background).name()
        tmp2 = "QTextEdit {background-color: "+self.defaultBackgroundColor+"}"
        tmp3 = "QListWidget {background-color: "+self.defaultBackgroundColor+"}"
        self.MessagesTextEdit.setStyleSheet(tmp2)        
        self.ProgramTextEdit.setStyleSheet(tmp2)     
        self.ProgramPreviewTextBox.setStyleSheet(tmp2)
        self.FilesListWidget.setStyleSheet(tmp3)        
        if("MCU" in platform.node()):
            self.theDFMGroup = DFMGroup.DFMGroup(COMM.UARTCOMM())
        else:
            self.theDFMGroup = DFMGroup.DFMGroup(COMM.TESTCOMM())          
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
       
        self.DFMButtons = []
        self.UpdateProgramGUI()

        self.main_widget = QtWidgets.QWidget(self)
        self.theDFMDataPlot = DFMPlot.MyDFMDataPlot(self.main_widget,backcolor=self.defaultBackgroundColor,width=5, height=4, dpi=100)        
        self.DFMPlotLayout.addWidget(self.theDFMDataPlot)   

        self.programDuration = datetime.timedelta(minutes=180)
        self.SetProgramStartTime(datetime.datetime.today())

        DFMGroup.DFMGroup.DFMGroup_updatecomplete+=self.UpdateDFMPlot
        self.toggleOutputsState=False

        self.MThread = GUIUpdateThread()
        self.MThread.updateGUISignal.connect(self.UpdateGUI)      
        self.MThread.start()

        self.FilesListWidget.currentItemChanged.connect(self.ProgramFileChoiceChanged)
        self.currentChosenProgramFile=""
        self.currentProgramFileDirectory=""

    def DisableButtons(self):        
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
        self.toggleOutputsAction.setEnabled(False)
        self.LoadProgramButton.setEnabled(False)

    def EnableButtons(self):        
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
        self.toggleOutputsAction.setEnabled(True)
        self.LoadProgramButton.setEnabled(True)

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
        if(len(self.theDFMGroup.theDFMs)==0): 
            self.StatusBar.showMessage("Load programs only after DFMs have been defined.",self.statusmessageduration)
            return
        sender = self.sender()
        tmp = sender.text()
        self.programStartTime = datetime.datetime.today() + datetime.timedelta(minutes=.1)
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
            return

        self.StatusBar.showMessage("Loaded basic program: " + tmp,self.statusmessageduration)
                            
    def ToggleProgramRun(self):
        if(len(self.theDFMGroup.theDFMs)==0): return
        if(self.theDFMGroup.currentProgram.isActive):
            self.RunProgramButton.setText("Run Program")
            self.theDFMGroup.StopCurrentProgram()
            self.toggleOutputsState=False
        else:
            self.DisableButtons()                        
            self.RunProgramButton.setText("Stop Program")      
            self.theDFMGroup.StageCurrentProgram()            
            self.toggleOutputsState=False
        self.UpdateDFMButtonTextColors()

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
        self.clearMessagesAction.triggered.connect(self.AssureClearMessages)
        self.aboutMCUAction.triggered.connect(self.AboutPyMCU)
        self.powerOffAction.triggered.connect(self.PowerOff)
        self.saveDataAction.triggered.connect(self.ChooseDataSaveLocation)
        self.deleteDataAction.triggered.connect(self.DeleteDataFolder)
        self.toggleOutputsAction.triggered.connect(self.ToggleOutputs)

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
        self.CustomButton.clicked.connect(self.LoadCustomProgram)
        self.LoadProgramButton.clicked.connect(self.LoadProgramClicked)
        self.refreshFilesButton.clicked.connect(self.LoadFilesListWidget)

    def ToggleOutputs(self):
        if(self.toggleOutputsState):
            for d in self.theDFMGroup.theDFMs:
                d.SetOutputsOff()
            self.toggleOutputsState = False
        else:
            for d in self.theDFMGroup.theDFMs:
                d.SetOutputsOn()
            self.toggleOutputsState = True

    def SetStartTimeNow(self):
        self.SetProgramStartTime(datetime.datetime.today())
        
        #self.programStartTime= tmp.toPyDateTime()


    def AboutPyMCU(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Flidea Master Control Unit")
        msg.setWindowTitle("About MCU")
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.connect(("google.com",80))    
            hostip=s.getsockname()[0]
        ss="Version 5.0\nIP: " + hostip
        msg.setInformativeText(ss)    
        msg.exec_()        

    def SetActiveDFM(self,num):
        self.activeDFMNum=num        
        self.activeDFM = self.theDFMGroup.theDFMs[self.activeDFMNum]        
        self.theDFMGroup.activeDFM = self.activeDFM       
        self.StatusBar.showMessage("Viewing " + str(self.activeDFM) +".",self.statusmessageduration)
        self.UpdateDFMButtonTextColors()

    def UpdateDFMButtonTextColors(self):        
        for i in range(0,len(self.theDFMGroup.theDFMs)):
            if(self.activeDFMNum==i):
                ss = 'QPushButton {font-weight:bold;'
            else:
                ss = 'QPushButton {'
            if(self.theDFMGroup.theDFMs[i].status==Enums.CURRENTSTATUS.READING):               
                ss+= 'color: black}' 
                self.DFMButtons[i].setStyleSheet(ss)                                
            elif(self.theDFMGroup.theDFMs[i].status==Enums.CURRENTSTATUS.RECORDING):
                ss+= 'color: green}' 
                self.DFMButtons[i].setStyleSheet(ss)
            elif(self.theDFMGroup.theDFMs[i].status==Enums.CURRENTSTATUS.ERROR):
                ss+= 'color: red}' 
                self.DFMButtons[i].setStyleSheet(ss)
            elif(self.theDFMGroup.theDFMs[i].status==Enums.CURRENTSTATUS.MISSING):
                ss+= 'color: blue}' 
                self.DFMButtons[i].setStyleSheet(ss)
            else:
                ss+= 'color: orange}' 
                self.DFMButtons[i].setStyleSheet(ss)                


    def DFMButtonClicked(self):
        sender = self.sender()
        for i in range(0,len(self.DFMButtons)):
            if sender is self.DFMButtons[i]:
                self.SetActiveDFM(i)   
                self.UpdateDFMPageGUI()                    

    def FindDFMs(self):   
        self.ClearDFM()
        self.StatusBar.showMessage("Searching for DFMs...",self.statusmessageduration)     
        self.ClearMessages()
        self.theDFMGroup.FindDFMs(5)            
        if(len(self.theDFMGroup.theDFMs)==0):
            self.StatusBar.showMessage("No DFMs found.",self.statusmessageduration)                            
            return
        self.findDFMAction.setEnabled(False)
        for d in self.theDFMGroup.theDFMs:
            s = str(d)
            tmp = QPushButton(s)
            tmp.setFlat(False)            
            tmp.setMinimumHeight(45)
            #tmp.setMaximumWidth(88)
            self.DFMListLayout2.setAlignment(Qt.AlignTop)
            self.DFMListLayout2.addWidget(tmp)            
            self.DFMButtons.append(tmp)             
        self.StatusBar.showMessage(str(len(self.theDFMGroup.theDFMs)) + " DFMs found.",self.statusmessageduration)                        
        for b in self.DFMButtons:
            b.clicked.connect(self.DFMButtonClicked)             
        self.programStartTime = datetime.datetime.today()
        self.programDuration = datetime.timedelta(minutes=180)
        self.LoadSimpleProgram()        
        self.SetActiveDFM(0)  
        self.UpdateDFMPageGUI()
        self.GotoDFMPage()     

    def DeleteDataFolder(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText("Are you sure that you would like to delete all data?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setWindowTitle("Delete Data")
        retval=msg.exec_()
        if(retval==QMessageBox.Yes):
            msg2 = QMessageBox()
            msg2.setIcon(QMessageBox.Question)
            msg2.setText("Are you REALLY sure ?")
            msg2.setWindowTitle("Delete Data")
            msg2.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            retval=msg2.exec_()
            if(retval==QMessageBox.Yes):
                os.system("rm -rf FLICData")  
            self.StatusBar.showMessage("Local data folder has been deleted.",self.statusmessageduration)                              

    def PowerOff(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setText("Are you sure that you would like to power off?")
        msg.setWindowTitle("Power Off")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        retval=msg.exec_()
        if(retval==QMessageBox.Yes):
            msg2 = QMessageBox()
            msg2.setIcon(QMessageBox.Question)
            msg2.setWindowTitle("Power Off")
            msg2.setText("Are you REALLY sure that you would like to power off?")
            msg2.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            retval=msg2.exec_()
            if(retval==QMessageBox.Yes):
                print("Shutting down")
                #os.system("shotdown /s /t 1)")

    def AssureClearMessages(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Clear Messages")
        msg.setText("Are you sure that you would like to clear messages?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        retval=msg.exec_()
        if(retval==QMessageBox.Yes):
            self.ClearMessages()
        
    def ClearMessages(self):       
        self.theDFMGroup.theMessageList.ClearMessages()        
        self.MessagesTextEdit.setText(str(self.theDFMGroup.theMessageList))    
    
    def ClearLayout(self,layout):
        while layout.count():
            child=layout.takeAt(0)
            if(child.widget()):
                child.widget().deleteLater()

    def ClearDFM(self):
        self.theDFMGroup.ClearDFMList()
        self.ClearLayout(self.DFMListLayout2)
        self.activeDFMNum=-1
        self.activeDFM=None
        self.DFMButtons.clear()
        self.UpdateProgramGUI()        
        self.findDFMAction.setEnabled(True)

    def GoToMessagesPage(self):
        self.StackedPages.setCurrentIndex(2)           

    def GoToProgramPage(self):        
        self.StackedPages.setCurrentIndex(0)
    
    def GotoDFMPage(self):
        self.StackedPages.setCurrentIndex(1)
     
    def GotoProgramLoadPage(self):  
        self.StackedPages.setCurrentIndex(3)

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
            self.CurrentStatusLabel.setText("Error")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.MISSING):
            self.CurrentStatusLabel.setText("Miss")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.READING):
            self.CurrentStatusLabel.setText("Read")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.RECORDING):
            self.CurrentStatusLabel.setText("Record")
        elif (self.activeDFM.status==Enums.CURRENTSTATUS.UNDEFINED):
            self.CurrentStatusLabel.setText("None")
        else:
            self.CurrentStatusLabel.setText("Huh?")

        if(self.activeDFM.pastStatus==Enums.PASTSTATUS.PASTERROR):
            self.PastStatusLabel.setText("Error")
        if(self.activeDFM.pastStatus==Enums.PASTSTATUS.ALLCLEAR):
            self.PastStatusLabel.setText("Clear")

        if(self.activeDFM.currentDFMErrors.GetI2CErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):            
            self.I2CErrorBox.setChecked(False)
        else:            
            self.I2CErrorBox.setChecked(True)

        if(self.activeDFM.currentDFMErrors.GetUARTErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.UARTErrorBox.setChecked(False)
        else:
            self.UARTErrorBox.setChecked(True)
         
        if(self.activeDFM.currentDFMErrors.GetPacketErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.PacketErrorBox.setChecked(False)
        else:
            self.PacketErrorBox.setChecked(True)
        if(self.activeDFM.currentDFMErrors.Getsi7021ErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.SIErrorBox.setChecked(False)
        else:
            self.SIErrorBox.setChecked(True)
        if(self.activeDFM.currentDFMErrors.GetTSL2591ErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.TSLErrorBox.setChecked(False)
        else:
            self.TSLErrorBox.setChecked(True)
        if(self.activeDFM.currentDFMErrors.GetConfigErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.ConfigErrorBox.setChecked(False)
        else:
            self.ConfigErrorBox.setChecked(True)
        if(self.activeDFM.currentDFMErrors.GetBufferErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.BufferErrorBox.setChecked(False)
        else:
            self.BufferErrorBox.setChecked(True)
        if(self.activeDFM.currentDFMErrors.GetMiscErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.MiscErrorBox.setChecked(False)
        else:
            self.MiscErrorBox.setChecked(True)

        self.UpdateDFMButtonTextColors()

    def UpdateDFMPlot(self):        
        if self.activeDFMNum>-1 and self.StackedPages.currentIndex()==1:                     
            #start = time.time()   
            self.theDFMDataPlot.UpdateFigure(self.activeDFM,self.theDFMGroup.currentProgram.autoBaseline)                
            #end=time.time()        
            #print("Plotting time: "+str(end-start))    
    
    def UpdateGUI(self):     
        if (self.theDFMGroup.currentProgram.isActive):           
            self.theDFMGroup.UpdateProgramStatus()         
            self.DisableButtons()
        else:
            self.EnableButtons()
        self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))                    
        if self.activeDFMNum>-1 and self.StackedPages.currentIndex()==1:                
            self.UpdateDFMPageGUI() 
        self.MessagesTextEdit.setText(str(self.theDFMGroup.theMessageList))               
        
            
    def closeEvent(self,event):
        self.MThread.StopThread()
        self.ClearDFM()

    def ProgramFileChoiceChanged(self,curr, prev):
        if(curr == None):
            return
        self.currentChosenProgramFile = curr.text()
        fn = self.currentProgramFileDirectory+self.currentChosenProgramFile
        f = open(fn,"r")
        lines=f.read()       
        self.ProgramPreviewTextBox.setText(lines)    

    def LoadProgramClicked(self):
        if(self.currentChosenProgramFile!=""):
            fn = self.currentProgramFileDirectory+self.currentChosenProgramFile
            try:              
                if(self.theDFMGroup.LoadTextProgram(fn)):
                    self.StatusBar.showMessage("Custom program loaded.",self.statusmessageduration) 
                    self.GoToProgramPage()
                else:  
                    self.StatusBar.showMessage("Problem loading program.",self.statusmessageduration)   
                self.UpdateProgramGUI() 
            except:
                self.StatusBar.showMessage("Problem loading program.",self.statusmessageduration)    

    def LoadFilesListWidget(self):
        self.FilesListWidget.clear()       
        subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]
        if len(subfolders)==0:
            self.currentProgramFileDirectory = "/media/pi/FLICPrograms/"
        else:
            self.currentProgramFileDirectory = subfolders[0]+"/FLICPrograms/"    

        files=(glob.glob(self.currentProgramFileDirectory+"*.txt"))
        for f in files:
            h, t = os.path.split(f)
            self.FilesListWidget.insertItem(0,t)
        if(len(files)>0):
            self.FilesListWidget.setCurrentRow(0)
    
    def LoadCustomProgram( self ): 
        self.LoadFilesListWidget()
        self.GotoProgramLoadPage()
        return
      
    def ChooseDataSaveLocation( self ):
        ''' Called when the user presses the Browse button
        '''
        dialog =QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
        dialog.setWindowTitle("Save Data")
        subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]
        if len(subfolders)==0:
            dialog.setDirectory("/media/pi")
        else:
            dialog.setDirectory(subfolders[0])
        if dialog.exec_():
            direct = dialog.selectedFiles()
            command = "cp -r FLICData/ " + direct[0]
            self.StatusBar.showMessage("Copying data files...",120000)                
            os.system(command)
            self.StatusBar.showMessage("Data copy complete.",self.statusmessageduration)                
        #options = QtWidgets.QFileDialog.Options()
        #options |= QtWidgets.QFileDialog.DontUseNativeDialog
        #fileName, _ = QtWidgets.QFileDialog.getExistingDirectory(
        #                None,
        #                "Choose Directory",
        #                "/media/pi")                      

        ## Donr forget to set programstarttime and duration here 
        ## aFTER THE program is loaded.
        


def main():   
    app = QtWidgets.QApplication(sys.argv)
    #app.setStyleSheet("QStatusBar.item {border : 0px black}")
    myapp = MyMainWindow()
    if("MCU" in platform.node()):
        myapp.showFullScreen()
    else:
        myapp.show()
       
    sys.exit(app.exec_())    
    print("Done")
    

    



if __name__ == "__main__":
    main()

