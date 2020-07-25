import sys
import fcntl
import struct
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from pyudev.pyqt5 import MonitorObserver
from pyudev import Context,Monitor
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
import subprocess
import glob
import shutil
import FLICDataCopy

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
    def __init__( self,pcb ):   
        self.theBoard=pcb    
        self.theDFMGroup = DFMGroup.DFMGroup(self.theBoard)
        super(MyMainWindow,self).__init__()        
        uic.loadUi("Mainwindow.ui",self)
        self.defaultBackgroundColor = self.DFMErrorGroupBox.palette().color(QtGui.QPalette.Background).name()
        tmp2 = "QTextEdit {background-color: "+self.defaultBackgroundColor+"}"
        tmp3 = "QListWidget {background-color: "+self.defaultBackgroundColor+"}"
        self.MessagesTextEdit.setStyleSheet(tmp2)        
        self.ProgramTextEdit.setStyleSheet(tmp2)     
        self.ProgramPreviewTextBox.setStyleSheet(tmp2)       
        self.FilesListWidget.setStyleSheet(tmp3)                    
        self.statusmessageduration=5000
        self.activeDFMNum=-1
        self.activeDFM=None                        
        self.MakeConnections()
        self.StackedPages.setCurrentIndex(1)
        self.statusLabel = QLabel()  
        self.statusLabel.setFont(QFont('Arial', 11))
        self.statusLabel.setFrameStyle(QFrame.NoFrame)
        self.statusLabel.setFrameShadow(QFrame.Plain)
        self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))
        self.StatusBar.addPermanentWidget(self.statusLabel)    
        self.StatusBar.setFont(QFont('Arial', 11))

        self.toolBar.setFont(QFont('Arial', 9))

        self.StatusBar.setStyleSheet('border: 0')
        self.StatusBar.setStyleSheet("QStatusBar::item {border: none;}")    
       
        self.DFMButtons = {}
        self.UpdateProgramGUI()
        self.DisableButtons()
        self.isUSBAttached=False

        self.main_widget = QtWidgets.QWidget(self)
        self.theDFMDataPlot = DFMPlot.MyDFMDataPlot(self.main_widget,backcolor=self.defaultBackgroundColor,width=5, height=4, dpi=100)        
        self.DFMPlotLayout.addWidget(self.theDFMDataPlot)   

        self.programDuration = datetime.timedelta(minutes=180)
        self.SetProgramStartTime(datetime.datetime.today())

        DFMGroup.DFMGroup.DFMGroup_updatecomplete+=self.UpdateDFMPlot
        DFMGroup.DFMGroup.DFMGroup_programEnded+=self.ProgramEnded
        self.toggleOutputsState=False

        self.MThread = GUIUpdateThread()
        self.MThread.updateGUISignal.connect(self.UpdateGUI)      
        self.MThread.start()

        self.FilesListWidget.currentItemChanged.connect(self.ProgramFileChoiceChanged)
        self.currentChosenProgramFile=""
        self.currentProgramFileDirectory=""

        self.context = Context()
        self.monitor = Monitor.from_netlink(self.context)
        self.monitor.filter_by(subsystem="usb")
        self.observer=MonitorObserver(self.monitor)
        self.observer.deviceEvent.connect(self.device_connected)
        self.monitor.start()

        self.fastUpdateCheckBox.setChecked(False)

        self.currentDFMType = Enums.DFMTYPE.PLETCHERV3

        self.isDataTransferring=False

        ## Check for USB upon startup
        try:
            subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]
            if len(subfolders)>0:
                self.isUSBAttached=True
                self.StatusBar.showMessage("USB connected...",2000)
                self.saveDataAction.setEnabled(True)
                self.MoveProgramButton.setEnabled(True)
                QApplication.processEvents()
        except:
            pass

    def device_connected(self,device):        
        if(device.action=="add"):
            self.isUSBAttached=True
            self.StatusBar.showMessage("USB connected...",2000)
            self.saveDataAction.setEnabled(True)
            self.MoveProgramButton.setEnabled(True)
            QApplication.processEvents()
        elif(device.action=="remove"):
            self.isUSBAttached=False
            self.StatusBar.showMessage("USB removed...",2000)
            self.saveDataAction.setEnabled(False)
            self.MoveProgramButton.setEnabled(False)
            QApplication.processEvents()

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
        self.MoveProgramButton.setEnabled(False)
        self.DeleteProgramButton.setEnabled(False)
      

    def EnableButtons(self):        
        self.clearDFMAction.setEnabled(True)
        if(self.isUSBAttached==True):            
            self.saveDataAction.setEnabled(True)        
            self.MoveProgramButton.setEnabled(True)
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
        self.DeleteProgramButton.setEnabled(True)

    def SetProgramStartTime(self,theTime):
        self.programStartTime = datetime.datetime.today() + datetime.timedelta(minutes=1)            
        self.programEndTime = self.programStartTime + self.programDuration        
        qtDate=QtCore.QDateTime.currentDateTime()    
        ss=self.programStartTime.strftime("%m-%d-%Y %H:%M:%S")        
        qtDate = QtCore.QDateTime.fromString(ss,"MM-dd-yyyy HH:mm:ss")        
        self.StartTimeEdit.setDateTime(qtDate)
        self.theDFMGroup.currentProgram.startTime = self.programStartTime
        self.UpdateProgramGUI()
        self.StatusBar.showMessage("Set program start time: " + self.programStartTime.strftime("%m/%d/%Y %H:%M:%S") ,self.statusmessageduration)


    def SetSimpleProgramButtonClicked(self):
        if(len(self.theDFMGroup.theDFMs)==0): 
            self.StatusBar.showMessage("Load programs only after DFMs have been defined.",self.statusmessageduration)
            return
        sender = self.sender()
        tmp = sender.text()
        #self.programStartTime = datetime.datetime.today() + datetime.timedelta(minutes=1)
        self.programStartTime = datetime.datetime.today() + datetime.timedelta(seconds=10)
        if(tmp == "30 min"):
            self.programDuration = datetime.timedelta(minutes=30)          
            self.LoadSimpleProgram()  
        elif(tmp == "60 min"):
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
        else:
            return

        self.StatusBar.showMessage("Loaded basic program: " + tmp,self.statusmessageduration)
                            
    def ToggleProgramRun(self):
        if(len(self.theDFMGroup.theDFMs)==0): return
        if(self.theDFMGroup.currentProgram.isActive):
            self.RunProgramButton.setEnabled(False)
            self.StatusBar.showMessage("Stopping program.",self.statusmessageduration)   
            QApplication.processEvents()            
            self.theDFMGroup.StopCurrentProgram()
            while self.theDFMGroup.currentProgram.isActive:
                pass
            self.RunProgramButton.setText("Run Program")
            self.toggleOutputsState=False
            self.RunProgramButton.setEnabled(True)                          
            self.fastUpdateCheckBox.setChecked(False)

        else:
            self.RunProgramButton.setEnabled(False)
            self.DisableButtons()                        
            QApplication.processEvents()            
            self.theDFMGroup.StageCurrentProgram()    
            self.StatusBar.showMessage("Staging program.",self.statusmessageduration)           
            self.toggleOutputsState=False
            self.RunProgramButton.setText("Stop Program")      
            self.RunProgramButton.setEnabled(True)
            self.fastUpdateCheckBox.setChecked(False)

        self.UpdateDFMButtonTextColors()
        self.GotoDFMPage()     

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
        self.saveDataAction.triggered.connect(self.SaveDataToUSB)
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
        self.MoveProgramButton.clicked.connect(self.MoveProgramFilesToLocal)
        self.DeleteProgramButton.clicked.connect(self.DeleteProgramFile)

        self.fastUpdateCheckBox.stateChanged.connect(self.FastUpdatesChanged)

  
    def ToggleOutputs(self):
        if(self.toggleOutputsState):
            for d in self.theDFMGroup.theDFMs.values():
                d.SetOutputsOff()
            self.toggleOutputsState = False
            self.StatusBar.showMessage("Outputs toggled off.",self.statusmessageduration)  
        else:
            for d in self.theDFMGroup.theDFMs.values():
                d.SetOutputsOn()
            self.toggleOutputsState = True
            self.StatusBar.showMessage("Outputs toggled on.",self.statusmessageduration)  

    def SetStartTimeNow(self):
        self.SetProgramStartTime(datetime.datetime.today())        
        #self.programStartTime= tmp.toPyDateTime()

    def AboutPyMCU(self):      
        stat = os.statvfs("./MainViewModel.py")
        availableMegaBytes=(stat.f_bfree*stat.f_bsize)/1048576
        try: 
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            hostip= s.getsockname()[0]
        except:
            hostip="unknown"
        
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setText("Flidea Master Control Unit")
        msg.setWindowTitle("About MCU")
        ss="Version: 1.0.0 beta\nIP: " + hostip
        ss=ss+"\nStorage: " + str(int(availableMegaBytes)) +" MB"
        msg.setInformativeText(ss)    
        msg.exec_()   

    def SetActiveDFM(self,num):       
        self.activeDFMNum=num              
        self.theDFMGroup.SetActiveDFM(self.activeDFMNum)
        self.activeDFM = self.theDFMGroup.activeDFM 
        
        if self.theDFMGroup.isWriting:          
            if(self.fastUpdateCheckBox.isChecked()):
                self.theDFMGroup.SetFastProgramReadInterval()            
            else:
                self.theDFMGroup.SetNormalProgramReadInterval()
        self.StatusBar.showMessage("Viewing " + str(self.activeDFM) +".",self.statusmessageduration)
        self.UpdateDFMButtonTextColors()

    def UpdateDFMButtonTextColors(self):        
        for key, value in self.theDFMGroup.theDFMs.items():
            if(self.activeDFMNum==key):
                ss = 'QPushButton {font-weight:bold;'
            else:
                ss = 'QPushButton {'
            if(value.status==Enums.CURRENTSTATUS.READING):               
                ss+= 'color: black}' 
                self.DFMButtons[key].setStyleSheet(ss)                                
            elif(value.status==Enums.CURRENTSTATUS.RECORDING):
                ss+= 'color: green}' 
                self.DFMButtons[key].setStyleSheet(ss)
            elif(value.status==Enums.CURRENTSTATUS.ERROR):
                ss+= 'color: red}' 
                self.DFMButtons[key].setStyleSheet(ss)
            elif(value.status==Enums.CURRENTSTATUS.MISSING):
                ss+= 'color: blue}' 
                self.DFMButtons[key].setStyleSheet(ss)
            else:
                ss+= 'color: orange}' 
                self.DFMButtons[key].setStyleSheet(ss)                


    def DFMButtonClicked(self):
        sender = self.sender()
        for key, value in self.DFMButtons.items():
            if sender is value:
                self.SetActiveDFM(key)   
                self.UpdateDFMPageGUI()                    

    def SetDFMTypeGUI(self):
        if(self.currentDFMType==Enums.DFMTYPE.PLETCHERV3):
            return
        self.DFMErrorGroupBox.setEnabled(False)


    def FindDFMs(self):   
        self.ClearDFM()
        self.StatusBar.showMessage("Searching for DFMs...",self.statusmessageduration)     
        self.ClearMessages()
        self.theDFMGroup.FindDFMs(10)                      
        if(len(self.theDFMGroup.theDFMs)==0):
            self.StatusBar.showMessage("No DFMs found.",self.statusmessageduration)                            
            return
        self.findDFMAction.setEnabled(False)
        for key, value in self.theDFMGroup.theDFMs.items():
            s = str(value)
            tmp = QPushButton(s)
            tmp.setFlat(False)            
            tmp.setMinimumHeight(45)
            #tmp.setMaximumWidth(88)
            self.DFMListLayout2.setAlignment(Qt.AlignTop)
            self.DFMListLayout2.addWidget(tmp)            
            self.DFMButtons[key]=tmp
        
        
        self.StatusBar.showMessage(str(len(self.theDFMGroup.theDFMs)) + " DFMs found.",self.statusmessageduration)                        
        for b in self.DFMButtons.values():
            b.clicked.connect(self.DFMButtonClicked)             
        self.programStartTime = datetime.datetime.today()
        self.programDuration = datetime.timedelta(minutes=180)        


        tmp = list(self.theDFMGroup.theDFMs.keys())[0]
        self.currentDFMType = self.theDFMGroup.theDFMs[tmp].DFMType
        self.SetDFMTypeGUI()        

        self.LoadSimpleProgram()        
        self.SetActiveDFM(self.theDFMGroup.currentDFMKeysList[0])    

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
                self.theDFMGroup.MP.StopReading()                                 
                #QCoreApplication.instance().quit()
                subprocess.call("sudo nohup shutdown -h now", shell=True)

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

        if(self.activeDFM.pastStatus==Enums.PASTSTATUS.PASTERROR):
            self.PastStatusLabel.setText("Error")
        if(self.activeDFM.pastStatus==Enums.PASTSTATUS.ALLCLEAR):
            self.PastStatusLabel.setText("Clear")

        if(self.activeDFM.currentDFMErrors.GetI2CErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):            
            self.I2CErrorBox.setChecked(False)
        else:            
            self.I2CErrorBox.setChecked(True)

        if(self.activeDFM.currentDFMErrors.GetOERRErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.OERRErrorBox.setChecked(False)
        else:
            self.OERRErrorBox.setChecked(True)
         
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
        if(self.activeDFM.currentDFMErrors.GetFERRErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.FERRErrorBox.setChecked(False)
        else:
            self.FERRErrorBox.setChecked(True)
        if(self.activeDFM.currentDFMErrors.GetInterruptErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.InterruptErrorBox.setChecked(False)
        else:
            self.InterruptErrorBox.setChecked(True)
        if(self.activeDFM.currentDFMErrors.GetMiscErrorStatus()==Enums.REPORTEDERRORSTATUS.NEVER):
            self.MiscErrorBox.setChecked(False)
        else:
            self.MiscErrorBox.setChecked(True)

        self.UpdateDFMButtonTextColors()

    def ProgramEnded(self):
        self.RunProgramButton.setText("Run Program")
        self.toggleOutputsState=False
        self.RunProgramButton.setEnabled(True)                          
        self.fastUpdateCheckBox.setChecked(False)

    def UpdateDFMPlot(self):           
        if self.activeDFMNum>0 and self.StackedPages.currentIndex()==1:                     
            #start = time.time()                          
            self.theDFMDataPlot.UpdateFigure(self.activeDFM,self.theDFMGroup.currentProgram.autoBaseline)                
            #end=time.time()        
            #print("Plotting time: "+str(end-start))    
    
    def UpdateGUI(self):     
        if (self.theDFMGroup.currentProgram.isActive):           
            self.theDFMGroup.UpdateProgramStatus()         
            self.DisableButtons()
            if(self.theDFMGroup.isWriting):
                self.fastUpdateCheckBox.setEnabled(True)
            else:
                self.fastUpdateCheckBox.setEnabled(False)

            ## This is here because sometimes a program update action will turn the
            ## readinterval back to normal.  So the checkbox has to show that when it happens.
            if(self.fastUpdateCheckBox.isChecked() and self.theDFMGroup.GetProgramReadInterval() != "fast"):
                self.fastUpdateCheckBox.setChecked(False)

        else:
            self.EnableButtons()           
            self.fastUpdateCheckBox.setEnabled(False)
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
        else:
            self.StatusBar.showMessage("No program chosen.",self.statusmessageduration)    


    def DeleteProgramFile(self):
        if(self.currentChosenProgramFile!=""):
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Question)
            msg.setText("Are you sure that you would like to delete this program file?")
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setWindowTitle("Delete Program")
            retval=msg.exec_()
            if(retval==QMessageBox.Yes):
                fn = self.currentProgramFileDirectory+self.currentChosenProgramFile
                try:              
                    os.remove(fn)
                    self.StatusBar.showMessage("Program deleted.",self.statusmessageduration) 
                    self.LoadFilesListWidget()
                except:
                    self.StatusBar.showMessage("Problem deleting program.",self.statusmessageduration) 
        else:
            self.StatusBar.showMessage("No program chosen.",self.statusmessageduration)      

    ## This function is not used anymore.
    def LoadFilesListWidgetDEPRICATED(self):
        self.FilesListWidget.clear()   
        try:    
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
        except:
            self.StatusBar.showMessage("Problem loading program. Is USB connected?",self.statusmessageduration)  
    
    def MoveProgramFilesToLocal(self):
        self.StatusBar.showMessage("Moving programs from USB...",self.statusmessageduration)  
        try:    
            subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]
            if len(subfolders)==0:
                sourceDirectory = "/media/pi/FLICPrograms/"
            else:
                sourceDirectory = subfolders[0]+"/FLICPrograms/"    
            targetDirectory ="./FLICPrograms/"    
            files=(glob.glob(sourceDirectory+"*.txt"))
            if(len(files)>0):
                for i in files:
                    shutil.copy(i,targetDirectory)
            else:
                self.StatusBar.showMessage("No .txt files found.",self.statusmessageduration)  
                
        except:
            self.StatusBar.showMessage("Problem moving programs. Is USB connected?",self.statusmessageduration)  
        sss="Move complete. {:d} program files moved.".format(len(files))
        self.StatusBar.showMessage(sss,self.statusmessageduration)  
        self.LoadCustomProgram()

    
    def LoadFilesListWidget(self):
        self.FilesListWidget.clear()       
        self.currentProgramFileDirectory ="./FLICPrograms/"    

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

    def DataTransferFunction(self):
        self.isDataTransferring=True
        try:
            command = 'cp -r FLICData/ "' + subfolders[0] +'"'   
            os.system(command)        
        except:
            self.isDataTransferring=False
        self.isDataTransferring=False

    def SaveDataToUSB( self ):
        subfolders = [f.path for f in os.scandir("/media/pi") if f.is_dir()]
        if len(subfolders)==0:
            self.StatusBar.showMessage("USB not found.",self.statusmessageduration)  
            return
        else:                                      
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Do not remove USB until copy is noted as complete.")
            msg.setWindowTitle("Data Transfer")
            msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)            
            ss="This may take several minutes.\nPress Okay to begin."
            msg.setInformativeText(ss)    
            returnVal=msg.exec_()  
            
            QApplication.processEvents()
            if returnVal==QMessageBox.Ok:   
                self.GoToMessagesPage()                            
                self.StatusBar.showMessage("Copying data files...",120000)      
                self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copying data, do not remove USB.", Enums.MESSAGETYPE.NOTICE)          
                self.MessagesTextEdit.setText(str(self.theDFMGroup.theMessageList))         
                QApplication.processEvents()              
                destPath = subfolders[0]+'/FLICData'    
                sourcePath="/home/pi/PyMCU/PyMCU/FLICData"                
                tmp=FLICDataCopy.FLICDataCopy("Copying files: ")                
                tmp.StartDataTransfer(sourcePath,destPath)     
                while(tmp.isDataTransferring):
                    self.StatusBar.showMessage(tmp.GetProgressString(),self.statusmessageduration)
                    QApplication.processEvents()  
                    time.sleep(0.2)      
                if(tmp.copySuccess):
                    self.StatusBar.showMessage("Data copy complete.",self.statusmessageduration)  
                    self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copying complete.", Enums.MESSAGETYPE.NOTICE)  
                else:
                    self.StatusBar.showMessage("Data copy failed.",self.statusmessageduration)  
                    self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copy failed!", Enums.MESSAGETYPE.ERROR)                  
            else:
                self.StatusBar.showMessage("Data copy canceled.",self.statusmessageduration)                
        try:
            command = "umount " + '"'+subfolders[0]+'"'
            os.system(command)    
            self.isUSBAttached=False            
            self.saveDataAction.setEnabled(False)
            self.MoveProgramButton.setEnabled(False)
            QApplication.processEvents()
        except:
            return


    def FastUpdatesChanged(self):
        if(self.theDFMGroup.isWriting==False):
            ## This shouldn't happen.  Just here to catch strange event.
            self.StatusBar.showMessage("Fast updates are allowed only during recording.",self.statusmessageduration)  
            self.fastUpdateCheckBox.setChecked(False)
            return 
        if(self.fastUpdateCheckBox.isChecked()):            
            self.theDFMGroup.SetFastProgramReadInterval()            
        else:            
            self.theDFMGroup.SetNormalProgramReadInterval()


    

def ModuleTest():
    Board.BoardSetup()
    tmp = DFMGroup.DFMGroup()
    tmp.FindDFMs(maxNum=7)
    counter=0
    while counter<10800:
        while tmp.MP.message_q.empty() != True:
            tmp2 = tmp.MP.message_q.get()
            print(tmp2.message)      
        QApplication.processEvents()
        time.sleep(1)

    tmp.StopReadWorker()
    time.sleep(1)
    
    #print("DFMs Found:" + str(len(tmp.theDFMs)))
    #tmp.LoadSimpleProgram(datetime.datetime.today(),datetime.timedelta(minutes=3))
    #print(tmp.currentProgram)
    #tmp.ActivateCurrentProgram()      
    #while(1):        
    #    tmp.theDFMs[0].ReadValues(True)
    #    print(tmp.theDFMs[0].theData.GetLastDataPoint().GetConsolePrintPacket())   
    #    time.sleep(1)      
    #    tmp.UpdateDFMStatus()     
    #    print(tmp.longestQueue)
    #    time.sleep(1)
    


def main():
    if("MCU" in platform.node()):
        theBoard=Board.BoardSetup()  
    
    app = QtWidgets.QApplication(sys.argv)
    #app.setStyleSheet("QStatusBar.item {border : 0px black}")
    myapp = MyMainWindow(theBoard)
    #ModuleTest()    
    myapp.showFullScreen()
    sys.exit(app.exec_()) 
    print("Done")
    

if __name__ == "__main__":
    main()
    


