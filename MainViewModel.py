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
if(platform.node()=="raspberrypi"):
    import RPi.GPIO as GPIO


#class MyMainWindow(QMainWindow, Ui_MainWindow ):
class MyMainWindow(QtWidgets.QMainWindow):
    def __init__( self ):       
        super(MyMainWindow,self).__init__()        
        uic.loadUi("Mainwindow.ui",self)
        self.theDFMGroup = DFMGroup.DFMGroup(COMM.TESTCOMM())
        #self.theDFMGroup = DFMGroup.DFMGroup(COMM.UARTCOMM())
                        
        self.MakeConnections()
        self.StackedPages.setCurrentIndex(1)
        self.statusLabel = QLabel()  
        self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))
        self.StatusBar.addWidget(self.statusLabel)
        guiThread = threading.Thread(target=self.UpdateGUI)
        guiThread.start()
        
    def setupUi( self, MW ):
        ''' Setup the UI of the super class, and add here code
        that relates to the way we want our UI to operate.
        '''
        super().setupUi( MW )

        # close the lower part of the splitter to hide the 
        # debug window under normal operations
        #self.splitter.setSizes([300, 0])
  
    def MakeConnections(self):
        self.DFM1Button.clicked.connect(self.DFM1ClickedSlot)
        self.powerOffAction.triggered.connect(self.DFM1ClickedSlot)
        self.messagesAction.triggered.connect(self.GoToMessagesPage)
        self.findDFMAction.triggered.connect(self.FindDFMs)

    def FindDFMs(self):
        print("Finding DFM")
        self.theDFMGroup.FindDFMs(4)
        


    # slot
    def returnPressedSlot( self ):
        ''' Called when the user enters a string in the line edit and
        presses the ENTER key.
        '''
        self.debugPrint( "RETURN key pressed in LineEdit widget" )

    # slot
    def DFM1ClickedSlot( self ):
        ''' Called when the user presses the Write-Doc button.
        '''
        print(self.sender().objectName())      
        self.StatusBar.showMessage("Hi there dude!!",2000)  
        self.browseSlot()

    def GoToMessagesPage(self):
        print("Messages")
        self.StackedPages.setCurrentIndex(2)
    def UpdateGUI(self):
        while True:
            self.statusLabel.setText(datetime.datetime.today().strftime("%B %d,%Y %H:%M:%S"))
            time.sleep(1)

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
    myapp = MyMainWindow()
    myapp.show()
    #myapp.showFullScreen()
    #MainWindow = QtWidgets.QMainWindow()
    #ui = MainWindowUIClass()
    #ui.setupUi(MainWindow)
    #ui.MakeConnections()
    #MainWindow.show()
    sys.exit(app.exec_())

    


if __name__ == "__main__":
    main()


