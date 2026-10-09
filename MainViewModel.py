import sys
from PyQt6 import QtCore, QtGui, QtWidgets, uic
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
import pyudev
import datetime
import getpass
import time
import platform
import DFMGroup
import Enums
import Board
import DFMPlot
import socket
import os
import subprocess
import glob
import shutil
import FLICDataCopy
from TimeInputDialog import DateDialog

APP_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Durations of the simple program buttons, by button text.
SIMPLE_PROGRAM_MINUTES = {"30 min":30, "60 min":60, "3 hours":180, "6 hours":360, "12 hours":720, "24 hours":1440, "5 days":7200}

# DFM button text color for each status, as (light theme, dark theme).
STATUS_COLORS = {
    Enums.CURRENTSTATUS.READING: ("black","white"),
    Enums.CURRENTSTATUS.RECORDING: ("green","green"),
    Enums.CURRENTSTATUS.ERROR: ("red","red"),
    Enums.CURRENTSTATUS.MISSING: ("blue","blue"),
}

STATUS_LABELS = {
    Enums.CURRENTSTATUS.ERROR: "Error",
    Enums.CURRENTSTATUS.MISSING: "Miss",
    Enums.CURRENTSTATUS.READING: "Read",
    Enums.CURRENTSTATUS.RECORDING: "Record",
    Enums.CURRENTSTATUS.UNDEFINED: "None",
}

def GetUSBDrives():
    """Mount points of attached USB drives. Raspberry Pi OS mounts them under /media/<user>;
    /media/pi is checked too for systems set up with that symlink."""
    drives = []
    for root in dict.fromkeys(os.path.realpath(r) for r in ("/media/pi", "/media/"+getpass.getuser())):
        try:
            drives += [f.path for f in os.scandir(root) if f.is_dir()]
        except OSError:
            pass
    return drives

class USBMonitorThread(QThread):
    usb_event = pyqtSignal(str)

    def run(self):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='usb')
        for device in iter(monitor.poll, None):
            if device.action in ('add','remove'):
                self.usb_event.emit(device.action)

class MyMainWindow(QtWidgets.QMainWindow):
    # The DFM group announces new data from its worker threads. Re-emitting it as a Qt signal
    # moves the plot update onto the GUI thread, the only thread allowed to redraw widgets.
    plotUpdateRequested = pyqtSignal()

    def InitializeGUI(self):
        uic.loadUi("Mainwindow.ui",self)
        self.defaultBackgroundColor = self.DFMErrorGroupBox.palette().color(QtGui.QPalette.ColorRole.Window).name()
        tmp2 = "QTextEdit {background-color: "+self.defaultBackgroundColor+"}"
        tmp3 = "QListWidget {background-color: "+self.defaultBackgroundColor+"}"
        self.MessagesTextEdit.setStyleSheet(tmp2)
        self.ProgramTextEdit.setStyleSheet(tmp2)
        self.ProgramPreviewTextBox.setStyleSheet(tmp2)
        self.FilesListWidget.setStyleSheet(tmp3)
        self.statusLabel = QLabel()
        self.statusLabel.setFont(QFont('Arial', 11))
        self.statusLabel.setFrameStyle(QFrame.Shape.NoFrame)
        self.statusLabel.setFrameShadow(QFrame.Shadow.Plain)
        self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))
        self.StatusBar.addPermanentWidget(self.statusLabel)
        self.StatusBar.setFont(QFont('Arial', 11))

        self.toolBar.setFont(QFont('Arial', 9))

        self.StatusBar.setStyleSheet('border: 0')
        self.StatusBar.setStyleSheet("QStatusBar::item {border: none;}")

        self.EnvironmentGroupBox.setEnabled(False)

        self.StackedPages.setCurrentIndex(1)

    def __init__( self,pcb,is_theme_dark):
        self.theBoard=pcb
        self.theDFMGroup = DFMGroup.DFMGroup(self.theBoard)
        super(MyMainWindow,self).__init__()
        self.InitializeGUI()
        self.statusmessageduration=5000
        self.activeDFMNum=-1
        self.activeDFM=None
        self.MakeConnections()

        self.DFMButtons = {}
        self.UpdateProgramGUI()
        self.isUSBAttached=False
        self.DisableButtons()

        self.main_widget = QtWidgets.QWidget(self)
        self.theDFMDataPlot = DFMPlot.MyDFMDataPlot(self.main_widget,backcolor=self.defaultBackgroundColor,width=5, height=4, dpi=100)
        self.DFMPlotLayout.addWidget(self.theDFMDataPlot)

        self.programDuration = datetime.timedelta(minutes=180)
        self.SetProgramStartTime(datetime.datetime.today())

        self.plotUpdateRequested.connect(self.UpdateDFMPlot)
        DFMGroup.DFMGroup.DFMGroup_updatecomplete+=self.plotUpdateRequested.emit
        DFMGroup.DFMGroup.DFMGroup_programEnded+=self.ProgramEnded
        DFMGroup.DFMGroup.DFMGroup_message+=self.NewDFMMessage
        self.toggleOutputsState=False

        self.FilesListWidget.currentItemChanged.connect(self.ProgramFileChoiceChanged)
        self.currentChosenProgramFile=""
        self.currentProgramFileDirectory=""

        self.usb_monitor_thread = USBMonitorThread()
        self.usb_monitor_thread.usb_event.connect(self.device_connected)
        self.usb_monitor_thread.start()

        self.fastUpdateCheckBox.setChecked(False)
        self.zoomPlotCheckBox.setChecked(False)

        self.updateButton.setEnabled(False)

        self.currentDFMType = Enums.DFMTYPE.PLETCHERV3

        self.isMessageUpdateNeeded=False

        ## Check for USB upon startup
        if(len(GetUSBDrives())>0):
            self.SetUSBAttached(True)

        self.is_theme_dark=is_theme_dark
        ## Only need to skip first check if it happens automatically
        self.firstThemeCheck=is_theme_dark
        self.darkThemeCheckBox.setChecked(is_theme_dark)

        # Runs the program schedule and refreshes the display once a second.
        self.guiTimer = QtCore.QTimer(self)
        self.guiTimer.timeout.connect(self.UpdateGUI)
        self.guiTimer.start(1000)
        QtCore.QTimer.singleShot(0,self.UpdateGUI)

        self.CheckForLowStorageWarning()

    def _MessageBox(self,icon,title,text,informativeText=None,buttons=None):
        # On Wayland a dialog stays in front only with a parent and these window flags, and the
        # flags must be set after the parent (see NotesForPI5).
        msg = QMessageBox()
        msg.setParent(self)
        msg.setIcon(icon)
        msg.setWindowTitle(title)
        msg.setText(text)
        if(informativeText is not None):
            msg.setInformativeText(informativeText)
        if(buttons is not None):
            msg.setStandardButtons(buttons)
        msg.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        return msg

    def _Confirm(self,title,text):
        msg = self._MessageBox(QMessageBox.Icon.Question,title,text,buttons=QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        return msg.exec()==QMessageBox.StandardButton.Yes

    def device_connected(self,action):
        if(action=="add"):
            self.SetUSBAttached(True)
        elif(action=="remove"):
            self.SetUSBAttached(False)

    def SetUSBAttached(self,isAttached):
        self.isUSBAttached=isAttached
        self.StatusBar.showMessage("USB connected..." if isAttached else "USB removed...",2000)
        self.saveDataAction.setEnabled(isAttached)
        self.MoveProgramButton.setEnabled(isAttached)
        self.updateButton.setEnabled(isAttached)
        QApplication.processEvents()

    def _ControlsLockedDuringProgram(self):
        return [self.clearDFMAction, self.clearMessagesAction, self.deleteDataAction, self.powerOffAction,
                self.T30MinButton, self.T60MinButton, self.T3HrButton, self.T6HrButton, self.T12HrButton,
                self.T24HrButton, self.T5DButton, self.CustomButton, self.StartTimeNowButton, self.StartTimeEdit,
                self.toggleOutputsAction, self.LoadProgramButton, self.DeleteProgramButton, self.SetDateAndTimeButton]

    def DisableButtons(self):
        for control in self._ControlsLockedDuringProgram()+[self.saveDataAction,self.MoveProgramButton]:
            control.setEnabled(False)

    def EnableButtons(self):
        for control in self._ControlsLockedDuringProgram():
            control.setEnabled(True)
        if(self.isUSBAttached==True):
            self.saveDataAction.setEnabled(True)
            self.MoveProgramButton.setEnabled(True)

    def SetStartTimeNow(self):
        self.SetProgramStartTime(datetime.datetime.today()+datetime.timedelta(minutes=1))

    def ManualStartTimeChange(self):
        dt = self.StartTimeEdit.dateTime()
        dt=dt.toPyDateTime()
        dt = dt.replace(second=0,microsecond=0)
        self.SetProgramStartTime(dt)

    def SetProgramStartTime(self,theTime):
        self.programStartTime = theTime
        self.programEndTime = self.programStartTime + self.programDuration
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
        tmp = self.sender().text()
        # "Custom" is handled by LoadCustomProgram.
        if(tmp not in SIMPLE_PROGRAM_MINUTES):
            return
        self.programDuration = datetime.timedelta(minutes=SIMPLE_PROGRAM_MINUTES[tmp])
        self.LoadSimpleProgram()
        self.StatusBar.showMessage("Loaded basic program: " + tmp,self.statusmessageduration)

    def ToggleProgramRun(self):
        if(len(self.theDFMGroup.theDFMs)==0): return
        if(self.theDFMGroup.currentProgram.isActive):
            self.RunProgramButton.setEnabled(False)
            self.StatusBar.showMessage("Stopping program.",self.statusmessageduration)
            QApplication.processEvents()
            self.theDFMGroup.StopCurrentProgram()
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
        self.SetProgramStartTime(datetime.datetime.today() + datetime.timedelta(minutes=1))
        self.programEndTime = self.programStartTime + self.programDuration
        self.theDFMGroup.currentProgram.CreateSimpleProgram(self.programStartTime,self.programDuration)
        self.UpdateProgramGUI()

    def UpdateProgramGUI(self):
        if(len(self.theDFMGroup.theDFMs)>0):
            self.ProgramTextEdit.setText(self.theDFMGroup.currentProgram.GetProgramDescription())
        else:
            self.ProgramTextEdit.setText("No program loaded.")

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

        self.StartTimeEdit.dateTimeChanged.connect(self.ManualStartTimeChange)

        self.CustomButton.clicked.connect(self.LoadCustomProgram)
        self.LoadProgramButton.clicked.connect(self.LoadProgramClicked)
        self.refreshFilesButton.clicked.connect(self.LoadFilesListWidget)
        self.MoveProgramButton.clicked.connect(self.MoveProgramFilesToLocal)
        self.DeleteProgramButton.clicked.connect(self.DeleteProgramFile)
        self.updateButton.clicked.connect(self.RunUpdate)

        self.fastUpdateCheckBox.stateChanged.connect(self.FastUpdatesChanged)
        self.zoomPlotCheckBox.stateChanged.connect(self.ZoomPlotChanged)

        self.SetDateAndTimeButton.clicked.connect(self.SetTimeDialog)

        self.darkThemeCheckBox.stateChanged.connect(self.ThemeChanged)

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

    def SetTimeDialog(self):
        secs= DateDialog.getDateTime(self)
        if(secs==0):
            return
        ss1 = "'@"+str(secs)+"'"
        ss2 = "sudo hwclock --set --date=\"$(date --date="+ss1+")\""
        os.system(ss2)
        time.sleep(1)
        os.system("sudo hwclock -s")

    def GetFreeMegaBytes(self):
        stat = os.statvfs(APP_DIRECTORY)
        return (stat.f_bfree*stat.f_bsize)/1048576

    def AboutPyMCU(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                hostip= s.getsockname()[0]
        except OSError:
            print("Normal except: No internet")
            hostip="unknown"

        if(self.theBoard.IsDFMV2Board()):
            stext = "Flidea Master Control Unit (V2; P5)"
        else:
            stext = "Flidea Master Control Unit (V3; P5)"
        ss="Version: 2.0.0\nIP: " + hostip
        ss=ss+"\nStorage: " + str(int(self.GetFreeMegaBytes())) +" MB"
        msg = self._MessageBox(QMessageBox.Icon.Information,"About MCU",stext,ss)
        settingsButton = msg.addButton("Settings",QMessageBox.ButtonRole.YesRole)
        msg.addButton("Okay",QMessageBox.ButtonRole.NoRole)
        settingsButton.setEnabled(not self.theDFMGroup.currentProgram.isActive)
        msg.exec()
        if(msg.clickedButton()==settingsButton):
            self.GotoSettingsPage()

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
            colors = STATUS_COLORS.get(value.status,("orange","orange"))
            ss+= 'color: ' + colors[1 if self.is_theme_dark else 0] + '}'
            self.DFMButtons[key].setStyleSheet(ss)

    def DFMButtonClicked(self):
        sender = self.sender()
        for key, value in self.DFMButtons.items():
            if sender is value:
                self.SetActiveDFM(key)
                self.UpdateDFMPageGUI()

    def SetDFMTypeGUI(self):
        if(self.currentDFMType==Enums.DFMTYPE.PLETCHERV3 or self.currentDFMType==Enums.DFMTYPE.ENVMONV3):
            return
        self.DFMErrorGroupBox.setEnabled(False)

    def FindDFMs(self):
        self.ClearDFM()
        self.StatusBar.showMessage("Searching for DFMs. This can take several seconds.",self.statusmessageduration)
        QApplication.processEvents()
        QApplication.processEvents()
        self.ClearMessages()
        self.theDFMGroup.FindDFMs()
        if(len(self.theDFMGroup.theDFMs)==0):
            self.StatusBar.showMessage("No DFMs found.",self.statusmessageduration)
            return
        self.findDFMAction.setEnabled(False)
        for key, value in self.theDFMGroup.theDFMs.items():
            tmp = QPushButton(str(value))
            tmp.setFlat(False)
            tmp.setMinimumHeight(40)
            self.DFMListLayout2.setAlignment(Qt.AlignmentFlag.AlignTop)
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
        if(self._Confirm("Delete Data","Are you sure that you would like to delete all data?") and
           self._Confirm("Delete Data","Are you REALLY sure ?")):
            shutil.rmtree("FLICData",ignore_errors=True)
            self.StatusBar.showMessage("Local data folder has been deleted.",self.statusmessageduration)

    def CheckForLowStorageWarning(self):
        availableMegaBytes=self.GetFreeMegaBytes()
        if(availableMegaBytes>1000):
            return
        msg = self._MessageBox(QMessageBox.Icon.Information,"Low Storage","Warning: Local storage less than 1GB.",
                               "Storage: " + str(int(availableMegaBytes)) +" MB")
        msg.addButton("Okay",QMessageBox.ButtonRole.NoRole)
        msg.exec()

    def PowerOff(self):
        if(self._Confirm("Power Off","Are you sure that you would like to power off?") and
           self._Confirm("Power Off","Are you REALLY sure that you would like to power off?")):
            print("Shutting down")
            self.theDFMGroup.MP.StopReading()
            subprocess.call("sudo nohup shutdown -h now", shell=True)

    def AssureClearMessages(self):
        if(self._Confirm("Clear Messages","Are you sure that you would like to clear messages?")):
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
        self.ClearMessages()

    def GoToMessagesPage(self):
        self.StackedPages.setCurrentIndex(2)

    def GoToProgramPage(self):
        self.StackedPages.setCurrentIndex(0)

    def GotoDFMPage(self):
        self.StackedPages.setCurrentIndex(1)
        self.UpdateGUI()

    def GotoProgramLoadPage(self):
        self.StackedPages.setCurrentIndex(3)

    def GotoSettingsPage(self):
        self.StackedPages.setCurrentIndex(4)

    def UpdateDFMPageGUI(self):
        dfm = self.activeDFM
        self.TempLabel.setText("{:.1f}C".format(dfm.reportedTemperature))
        self.HumidLabel.setText("{:.1f}%".format(dfm.reportedHumidity))
        self.LUXLabel.setText("{:.1f}".format(dfm.reportedLUX))
        self.VoltsInLabel.setText("{:.2f}V".format(dfm.reportedVoltsIn))

        if(dfm.reportedTemperature + dfm.reportedHumidity+dfm.reportedLUX==0):
            self.EnvironmentGroupBox.setEnabled(False)
        else:
            self.EnvironmentGroupBox.setEnabled(True)

        if(dfm.reportedDarkState == Enums.DARKSTATE.ON):
            self.DarkModeLabel.setText("Yes")
        else:
            self.DarkModeLabel.setText("No")
        self.FrequencyLabel.setText("{:d}Hz".format(dfm.reportedOptoFrequency))
        self.PulseWidthLabel.setText("{:d}ms".format(dfm.reportedOptoPulsewidth))

        self.FirmwareLabel.setText(dfm.firmwareVersion)

        if (dfm.DFMType==Enums.DFMTYPE.PLETCHERV3 or dfm.DFMType==Enums.DFMTYPE.ENVMONV3):
            self.OptoStateLabel.setText("0x{:03X}".format(dfm.reportedOptoStateCol1))
        else:
            self.OptoStateLabel.setText("{:02X},{:02X}".format(dfm.reportedOptoStateCol1,dfm.reportedOptoStateCol2))

        self.CurrentStatusLabel.setText(STATUS_LABELS[dfm.status])
        if(dfm.pastStatus==Enums.PASTSTATUS.PASTERROR):
            self.PastStatusLabel.setText("Error")
        else:
            self.PastStatusLabel.setText("Clear")

        errors = dfm.currentDFMErrors
        for box, status in ((self.I2CErrorBox, errors.GetI2CErrorStatus()),
                            (self.OERRErrorBox, errors.GetOERRErrorStatus()),
                            (self.PacketErrorBox, errors.GetPacketErrorStatus()),
                            (self.SIErrorBox, errors.Getsi7021ErrorStatus()),
                            (self.TSLErrorBox, errors.GetTSL2591ErrorStatus()),
                            (self.FERRErrorBox, errors.GetFERRErrorStatus()),
                            (self.InterruptErrorBox, errors.GetInterruptErrorStatus()),
                            (self.MiscErrorBox, errors.GetMiscErrorStatus())):
            box.setChecked(status!=Enums.REPORTEDERRORSTATUS.NEVER)

        self.UpdateDFMButtonTextColors()

    def ProgramEnded(self):
        self.RunProgramButton.setText("Run Program")
        self.toggleOutputsState=False
        self.RunProgramButton.setEnabled(True)
        self.fastUpdateCheckBox.setChecked(False)

    def UpdateDFMPlot(self):
        if self.activeDFMNum>0 and self.StackedPages.currentIndex()==1:
            self.theDFMDataPlot.UpdateFigure(self.activeDFM,self.theDFMGroup.currentProgram.autoBaseline)

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
        if self.isMessageUpdateNeeded:
            self.MessagesTextEdit.setText(str(self.theDFMGroup.theMessageList))
            self.isMessageUpdateNeeded=False

    def NewDFMMessage(self,dummy):
        self.isMessageUpdateNeeded=True

    def closeEvent(self,event):
        self.guiTimer.stop()
        self.ClearDFM()

    def ProgramFileChoiceChanged(self,curr, prev):
        if(curr == None):
            return
        self.currentChosenProgramFile = curr.text()
        with open(self.currentProgramFileDirectory+self.currentChosenProgramFile,"r") as f:
            self.ProgramPreviewTextBox.setText(f.read())

    def LoadProgramClicked(self):
        if(self.currentChosenProgramFile!=""):
            fn = self.currentProgramFileDirectory+self.currentChosenProgramFile
            try:
                if(self.theDFMGroup.LoadTextProgram(fn)):
                    self.StatusBar.showMessage("Custom program loaded.",self.statusmessageduration)
                    self.GoToProgramPage()
                    if(self.theDFMGroup.CheckProgramCompatibility()==False):
                        self._MessageBox(QMessageBox.Icon.Information,"Compatibility Check","Warning: Check program compatibility!",
                                         "Version 1.5 DFM are not compatible with decay, delay, or maxtime values > 65536!").exec()
                else:
                    self.StatusBar.showMessage("Problem loading program.",self.statusmessageduration)
                self.UpdateProgramGUI()
            except Exception:
                print("Normal except: problem loading program")
                self.StatusBar.showMessage("Problem loading program.",self.statusmessageduration)
        else:
            self.StatusBar.showMessage("No program chosen.",self.statusmessageduration)

    def DeleteProgramFile(self):
        if(self.currentChosenProgramFile!=""):
            if(self._Confirm("Delete Program","Are you sure that you would like to delete this program file?")):
                fn = self.currentProgramFileDirectory+self.currentChosenProgramFile
                try:
                    os.remove(fn)
                    self.StatusBar.showMessage("Program deleted.",self.statusmessageduration)
                    self.LoadFilesListWidget()
                except OSError:
                    print("Normal except: problem deleting program")
                    self.StatusBar.showMessage("Problem deleting program.",self.statusmessageduration)
        else:
            self.StatusBar.showMessage("No program chosen.",self.statusmessageduration)

    def MoveProgramFilesToLocal(self):
        self.StatusBar.showMessage("Moving programs from USB...",self.statusmessageduration)
        drives = GetUSBDrives()
        try:
            if(len(drives)==0):
                raise OSError("No USB drive")
            files=glob.glob(drives[0]+"/FLICPrograms/*.txt")
            for i in files:
                shutil.copy(i,"./FLICPrograms/")
        except OSError:
            print("Normal except: problem moving program")
            self.StatusBar.showMessage("Problem moving programs. Is USB connected?",self.statusmessageduration)
            return
        if(len(files)==0):
            self.StatusBar.showMessage("No .txt files found.",self.statusmessageduration)
        else:
            sss="Move complete. {:d} program files moved.".format(len(files))
            self.StatusBar.showMessage(sss,self.statusmessageduration)
        self.LoadCustomProgram()

    def LoadFilesListWidget(self):
        self.FilesListWidget.clear()
        self.currentProgramFileDirectory ="./FLICPrograms/"
        files=(glob.glob(self.currentProgramFileDirectory+"*.txt"))
        files.sort(reverse=True)
        for f in files:
            h, t = os.path.split(f)
            self.FilesListWidget.insertItem(0,t)
        if(len(files)>0):
            self.FilesListWidget.setCurrentRow(0)

    def LoadCustomProgram( self ):
        self.LoadFilesListWidget()
        self.GotoProgramLoadPage()

    def SaveDataToUSB( self ):
        try:
            drives = GetUSBDrives()
            if len(drives)==0:
                self.StatusBar.showMessage("USB not found.",self.statusmessageduration)
                print("not found")
                return
            msg = self._MessageBox(QMessageBox.Icon.Warning,"Data Transfer","Do not remove USB until copy is noted as complete.",
                                   "This may take several minutes.\nPress Okay to begin.",
                                   QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            returnVal=msg.exec()

            QApplication.processEvents()
            if returnVal==QMessageBox.StandardButton.Ok:
                self.DisableButtons()
                self.GoToMessagesPage()
                self.StatusBar.showMessage("Copying data files...",120000)
                self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copying data, do not remove USB.", Enums.MESSAGETYPE.ANNOTATION)
                self.MessagesTextEdit.setText(str(self.theDFMGroup.theMessageList))
                QApplication.processEvents()
                destPath = drives[0]+'/FLICData'
                # Data is recorded to ./FLICData (see DFMGroup.WriteStarter).
                sourcePath=os.path.abspath("FLICData")
                tmp=FLICDataCopy.FLICDataCopy("Copying files: ")
                tmp.StartDataTransfer(sourcePath,destPath)
                while(tmp.isDataTransferring):
                    self.StatusBar.showMessage(tmp.GetProgressString(),self.statusmessageduration)
                    QApplication.processEvents()
                    time.sleep(0.2)
                if(tmp.copySuccess):
                    self.StatusBar.showMessage("Data copy complete.",self.statusmessageduration)
                    self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copying complete.", Enums.MESSAGETYPE.ANNOTATION)
                else:
                    self.StatusBar.showMessage("Data copy failed.",self.statusmessageduration)
                    self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copy failed!", Enums.MESSAGETYPE.ERROR)
                self.EnableButtons()
            else:
                self.StatusBar.showMessage("Data copy canceled.",self.statusmessageduration)

            command = "umount " + '"'+drives[0]+'"'
            os.system(command)
            self.isUSBAttached=False
            self.saveDataAction.setEnabled(False)
            self.MoveProgramButton.setEnabled(False)
            QApplication.processEvents()
            self.StatusBar.showMessage("USB unmounted. Ready to remove.",self.statusmessageduration)
        except Exception:
            print("Except: Problem saving data to USB.")
            self.StatusBar.showMessage("Problem saving data to USB.",self.statusmessageduration)
            return

    def ZoomPlotChanged(self):
        if(self.zoomPlotCheckBox.isChecked()):
            self.theDFMDataPlot.UpdateYAxisRange(0,100)
        else:
            self.theDFMDataPlot.UpdateYAxisRange(0,1000)

    def ThemeChanged(self):
        if(self.firstThemeCheck):
            self.firstThemeCheck=False
            return
        if(self.darkThemeCheckBox.isChecked()):
            with open('theme.txt', 'w') as file:
                file.write("dark")
            self.StatusBar.showMessage("Dark theme will activate next boot.",self.statusmessageduration)
        else:
            with open('theme.txt', 'w') as file:
                file.write("normal")
            self.StatusBar.showMessage("Light theme will activate next boot.",self.statusmessageduration)

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

    def RunUpdate(self):
        try:
            drives = GetUSBDrives()
            files = glob.glob(drives[0]+"/FLICUpdates/*.tgz") if drives else []
            if(len(files)==1):
                self.StatusBar.showMessage("Updating...",self.statusmessageduration)
                time.sleep(1)
                command = "/bin/tar -C \"" + APP_DIRECTORY + "\" -xvf " + "\""+files[0]+"\""
                os.system(command)
                self.StatusBar.showMessage("Update complete. Rebooting. Remove USB.",self.statusmessageduration)
                time.sleep(5)
                os.system("sudo shutdown -r now")
            else:
                self.StatusBar.showMessage("Update failed.",self.statusmessageduration)
                self.GotoDFMPage()
        except Exception:
            pass


def check_theme(app):
    try:
        with open('theme.txt', 'r') as file:
            first_word = file.readline().strip()
            if(first_word=="dark"):
                set_dark_theme(app)
                return True
            else:
                return False
    except Exception:
        return False

def set_dark_theme(app):
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(palette)

def main():
    if("MCU" in platform.node()):
        theBoard=Board.BoardSetup()
    else:
        theBoard=Board.BoardMock()
    app = QtWidgets.QApplication(sys.argv)
    is_theme_dark=check_theme(app)
    myapp = MyMainWindow(theBoard,is_theme_dark)
    myapp.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
