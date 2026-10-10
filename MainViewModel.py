import sys
from PyQt6 import QtCore, QtGui, QtWidgets, uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
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
import shutil
import traceback
import FLICDataCopy
import MCUUpdate
from TimeInputDialog import DateDialog

APP_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
# Shown in the About box; keep in step with the version in pyproject.toml.
APP_VERSION = "3.5.0"

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
    /media/pi is checked too for systems set up with that symlink. Folders left behind by a
    drive that was pulled without unmounting are skipped: only real mount points count."""
    drives = []
    for root in dict.fromkeys(os.path.realpath(r) for r in ("/media/pi", "/media/"+getpass.getuser())):
        try:
            drives += [f.path for f in os.scandir(root) if f.is_dir() and os.path.ismount(f.path)]
        except OSError:
            pass
    return sorted(drives)

def GetUSBDrive(folder):
    """First attached USB drive that has the given top-level folder, or None.
    Drives without it (e.g. a second, unrelated stick) are ignored."""
    for drive in GetUSBDrives():
        if os.path.isdir(os.path.join(drive, folder)):
            return drive
    return None

def FindUpdateFiles():
    """Update packages (.mcu, or .tgz from older builds) at the top of any USB drive or in its
    FLICUpdates folder. Hidden files are skipped, e.g. the ._ copies a Mac leaves on FAT sticks."""
    found = []
    for drive in GetUSBDrives():
        for folder in (drive, os.path.join(drive,"FLICUpdates")):
            try:
                found += [f.path for f in os.scandir(folder) if f.is_file() and not f.name.startswith(".")
                          and f.name.lower().endswith((".mcu",".tgz"))]
            except OSError:
                pass
    return sorted(found)

def ListProgramFiles(directory):
    """Program files (.txt in any letter case, e.g. PROGRAM.TXT from Windows) in a folder."""
    try:
        return [f.path for f in os.scandir(directory) if f.is_file() and f.name.lower().endswith(".txt")]
    except OSError:
        return []

def RunAsRoot(*command):
    """Runs a command with sudo, never prompting for a password (see the sudoers step in
    docs/Pi5Setup.md). Returns an error message, or None on success."""
    try:
        result = subprocess.run(["sudo","-n",*command],capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired) as e:
        return str(e)
    if result.returncode!=0:
        return (result.stderr or result.stdout).strip() or "exit code "+str(result.returncode)
    return None

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
        self.isCopyingData=False
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

        self.fastUpdateCheckBox.setChecked(False)
        self.zoomPlotCheckBox.setChecked(False)

        self.currentDFMType = Enums.DFMTYPE.PLETCHERV3

        self.isMessageUpdateNeeded=False

        ## Check for USB upon startup; UpdateGUI keeps checking once a second.
        self.CheckUSB()

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
        # flags must be set after the parent (see docs/Pi5Setup.md).
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

    def CheckUSB(self):
        # Based on what is actually mounted, so other USB devices (keyboard, hub) coming and
        # going don't change it, and it can't get stuck after a missed event.
        isAttached = len(GetUSBDrives())>0
        if(isAttached!=self.isUSBAttached):
            self.isUSBAttached=isAttached
            self.StatusBar.showMessage("USB connected..." if isAttached else "USB removed...",2000)
            self.UpdateUSBButtons()

    def UpdateUSBButtons(self):
        # USB actions need a drive and are locked while a program runs or data is copying.
        isAllowed = self.isUSBAttached and not self.areButtonsLocked
        for control in (self.saveDataAction,self.MoveProgramButton,self.updateButton):
            control.setEnabled(isAllowed)

    def _ControlsLockedDuringProgram(self):
        return [self.clearDFMAction, self.clearMessagesAction, self.deleteDataAction, self.powerOffAction,
                self.T30MinButton, self.T60MinButton, self.T3HrButton, self.T6HrButton, self.T12HrButton,
                self.T24HrButton, self.T5DButton, self.CustomButton, self.StartTimeNowButton, self.StartTimeSetButton,
                self.toggleOutputsAction, self.LoadProgramButton, self.DeleteProgramButton, self.SetDateAndTimeButton]

    def DisableButtons(self):
        self.areButtonsLocked=True
        for control in self._ControlsLockedDuringProgram():
            control.setEnabled(False)
        self.UpdateUSBButtons()

    def EnableButtons(self):
        if(self.isCopyingData):
            return
        self.areButtonsLocked=False
        for control in self._ControlsLockedDuringProgram():
            control.setEnabled(True)
        self.UpdateUSBButtons()

    def SetStartTimeNow(self):
        self.SetProgramStartTime(datetime.datetime.today()+datetime.timedelta(minutes=1))

    def SetStartTimeClicked(self):
        initial = QtCore.QDateTime(self.programStartTime.replace(second=0,microsecond=0))
        secs = DateDialog.getDateTime(self,title="Program start time",okText="Set Start",initial=initial)
        if(secs==0):
            return
        self.SetProgramStartTime(datetime.datetime.fromtimestamp(secs))

    def SetProgramStartTime(self,theTime):
        self.programStartTime = theTime
        self.programEndTime = self.programStartTime + self.programDuration
        self.StartTimeLabel.setText(self.programStartTime.strftime("%m/%d/%Y %H:%M"))
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

        self.StartTimeSetButton.clicked.connect(self.SetStartTimeClicked)

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
        # Set the system clock, then write it to the Pi 5's built-in RTC (rtc0) so it survives
        # power-off on the RTC battery.
        newTime = datetime.datetime.fromtimestamp(secs).strftime("%Y-%m-%d %H:%M:%S")
        error = RunAsRoot("/usr/bin/date","-s","@"+str(secs))
        if(error is None):
            error = RunAsRoot("/usr/sbin/hwclock","-w")
        if(error is None):
            self.StatusBar.showMessage("Clock set to "+newTime+".",self.statusmessageduration)
        else:
            print("Setting the clock failed: "+error)
            self.StatusBar.showMessage("Clock not set: "+error,self.statusmessageduration)

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
        ss="Version: " + APP_VERSION + "\nIP: " + hostip
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
            error = RunAsRoot("/usr/sbin/shutdown","-h","now")
            if(error is not None):
                print("Power off failed: "+error)
                self.StatusBar.showMessage("Power off failed: "+error,self.statusmessageduration)

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

        # One checkbox per error bit, bit 0 first. What they show depends on the DFM's firmware.
        errors = dfm.currentDFMErrors
        boxes = (self.I2CErrorBox, self.OERRErrorBox, self.PacketErrorBox, self.SIErrorBox,
                 self.TSLErrorBox, self.FERRErrorBox, self.InterruptErrorBox, self.MiscErrorBox)
        self.LayOutErrorBoxes(boxes, errors.display)
        for box, entry in zip(boxes, errors.display):
            if(entry is None):
                continue
            label, description, bits = entry
            box.setText(label)
            box.setToolTip(description)
            box.setChecked(errors.GetStatus(bits)!=Enums.REPORTEDERRORSTATUS.NEVER)

        self.UpdateDFMButtonTextColors()

    def LayOutErrorBoxes(self, boxes, display):
        # Fill the grid slots in order (down the first column, then the second) with the boxes
        # in use, so a hidden one (e.g. bit 1 on firmware before 2.0.2) leaves no gap under
        # No Ack; any empty slot ends up last.
        if(getattr(self,"errorBoxDisplay",None) is display):
            return
        self.errorBoxDisplay = display
        layout = self.DFMErrorGroupBox.layout()
        slots = [(0,0),(1,0),(4,0),(5,0),(0,1),(1,1),(4,1),(5,1)]
        shown = [box for box, entry in zip(boxes, display) if entry is not None]
        for box in boxes:
            layout.removeWidget(box)
            box.setVisible(box in shown)
        for box, (row, col) in zip(shown, slots):
            layout.addWidget(box, row, col)

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
        self.CheckUSB()
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
        # Files saved on Windows may not be UTF-8 (e.g. a degree sign); show them anyway.
        try:
            with open(self.currentProgramFileDirectory+self.currentChosenProgramFile,"r",encoding="utf-8-sig",errors="replace") as f:
                self.ProgramPreviewTextBox.setText(f.read())
        except OSError as e:
            self.ProgramPreviewTextBox.setText("Cannot read this file: "+str(e))

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
        drive = GetUSBDrive("FLICPrograms")
        if drive is None:
            self.StatusBar.showMessage("No USB with a FLICPrograms folder found.",self.statusmessageduration)
            return
        try:
            files=ListProgramFiles(drive+"/FLICPrograms")
            os.makedirs("./FLICPrograms",exist_ok=True)
            for i in files:
                shutil.copyfile(i,os.path.join("./FLICPrograms",os.path.basename(i)))
        except OSError as e:
            print("Problem moving programs: "+str(e))
            self.StatusBar.showMessage("Problem moving programs: "+str(e),self.statusmessageduration)
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
        files=ListProgramFiles(self.currentProgramFileDirectory)
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
        drive = GetUSBDrive("FLICData")
        if drive is None:
            self.StatusBar.showMessage("No USB with a FLICData folder found.",self.statusmessageduration)
            return
        # Data is recorded to ./FLICData (see DFMGroup.WriteStarter).
        sourcePath=os.path.abspath("FLICData")
        tmp=FLICDataCopy.FLICDataCopy("Copying files: ")
        if(tmp.countFiles(sourcePath)==0):
            self.StatusBar.showMessage("No local data to copy.",self.statusmessageduration)
            return
        msg = self._MessageBox(QMessageBox.Icon.Warning,"Data Transfer","Do not remove USB until copy is noted as complete.",
                               "This may take several minutes.\nPress Okay to begin.",
                               QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if msg.exec()!=QMessageBox.StandardButton.Ok:
            # The drive stays mounted, so programs can still be moved or the copy retried.
            self.StatusBar.showMessage("Data copy canceled.",self.statusmessageduration)
            return

        self.DisableButtons()
        self.isCopyingData=True
        try:
            self.GoToMessagesPage()
            self.StatusBar.showMessage("Copying data files...",120000)
            self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copying data, do not remove USB.", Enums.MESSAGETYPE.ANNOTATION)
            self.MessagesTextEdit.setText(str(self.theDFMGroup.theMessageList))
            QApplication.processEvents()
            tmp.StartDataTransfer(sourcePath,drive+'/FLICData')
            while(tmp.isDataTransferring):
                self.StatusBar.showMessage(tmp.GetProgressString(),self.statusmessageduration)
                QApplication.processEvents()
                time.sleep(0.2)
            if(not tmp.copySuccess):
                print("Data copy failed: "+tmp.errorMessage)
                self.StatusBar.showMessage("Data copy failed: "+tmp.errorMessage,self.statusmessageduration)
                self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copy failed! "+tmp.errorMessage, Enums.MESSAGETYPE.ERROR)
                return

            # Flush everything to the stick before saying it can be removed.
            os.sync()
            result = subprocess.run(["umount",drive],capture_output=True,text=True)
            if(result.returncode==0):
                self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copying complete. USB unmounted.", Enums.MESSAGETYPE.ANNOTATION)
                self.StatusBar.showMessage("Data copy complete. USB unmounted, ready to remove.",self.statusmessageduration)
            else:
                error = result.stderr.strip()
                print("Unmount failed: "+error)
                self.theDFMGroup.NewMessage(0, datetime.datetime.today(), 0, "Copying complete, but USB did not unmount: "+error, Enums.MESSAGETYPE.ERROR)
                self.StatusBar.showMessage("Copy complete, but USB did not unmount. Wait, then remove it.",self.statusmessageduration)
        finally:
            self.isMessageUpdateNeeded=True
            self.isCopyingData=False
            self.EnableButtons()
            self.CheckUSB()

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
        # Package built by CreateVersion.sh: docs/Packaging.md (build), docs/Updating.md (install).
        files = FindUpdateFiles()
        if(len(files)!=1):
            reason = "No update file (.mcu) found on the USB." if len(files)==0 else \
                     "More than one update file on the USB ("+", ".join(os.path.basename(f) for f in files)+"); leave only one."
            self.StatusBar.showMessage("Update not started: "+reason,self.statusmessageduration)
            return
        error = MCUUpdate.CheckArchive(files[0])
        if(error):
            self.StatusBar.showMessage("Update not started: "+error,self.statusmessageduration)
            return
        newVersion = MCUUpdate.ReadArchiveVersion(files[0]) or "unknown"
        if(not self._Confirm("Update MCU","Install PyMCU "+newVersion+" from "+os.path.basename(files[0])+"?\n\n"+
                             "Installed now: "+APP_VERSION+". The MCU restarts when the update is done.")):
            self.StatusBar.showMessage("Update canceled.",self.statusmessageduration)
            return

        self.DisableButtons()
        self.StatusBar.showMessage("Updating to "+newVersion+"... do not remove USB or power.",600000)
        QApplication.processEvents()
        print("Installing update "+files[0]+" ("+APP_VERSION+" -> "+newVersion+")")
        success, message = MCUUpdate.InstallUpdate(files[0], APP_DIRECTORY)
        print("Update: "+message)
        if(not success):
            self.StatusBar.showMessage("Update failed: "+message,self.statusmessageduration)
            self.EnableButtons()
            return
        self.StatusBar.showMessage("Update to "+newVersion+" installed. Restarting... remove USB.",self.statusmessageduration)
        QApplication.processEvents()
        os.sync()
        time.sleep(3)
        error = RunAsRoot("/usr/sbin/shutdown","-r","now")
        if(error is not None):
            print("Reboot failed: "+error)
            self.StatusBar.showMessage("Update installed. Restart the MCU to use it.",self.statusmessageduration)
            self.EnableButtons()


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
    # Grey out disabled controls (and other-month days in the calendar).
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(127, 127, 127))
    app.setPalette(palette)

def LogException(excType,excValue,excTraceback):
    # PyQt6 aborts the whole app on an error inside a button or timer handler unless
    # sys.excepthook is replaced. Log it (RunMCU.sh sends output to mcu.log) and keep running.
    print(datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")+" Unhandled error:")
    traceback.print_exception(excType,excValue,excTraceback)
    sys.stdout.flush()

def main():
    sys.excepthook=LogException
    print(datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")+" PyMCU "+APP_VERSION+" starting")
    if("MCU" in platform.node()):
        theBoard=Board.BoardSetup()
    else:
        theBoard=Board.BoardMock()
    app = QtWidgets.QApplication(sys.argv)
    if("MCU" in platform.node()):
        # Touch-screen kiosk: no mouse cursor, even before the first touch.
        app.setOverrideCursor(Qt.CursorShape.BlankCursor)
    is_theme_dark=check_theme(app)
    myapp = MyMainWindow(theBoard,is_theme_dark)
    myapp.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
