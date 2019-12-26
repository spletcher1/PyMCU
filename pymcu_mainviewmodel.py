import sys
from PyQt5 import QtCore, QtGui, QtWidgets, uic
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from pymcu_mainwindow import Ui_MainWindow
import ../DFM


#class MyMainWindow(QMainWindow, Ui_MainWindow ):
class MyMainWindow(QtWidgets.QMainWindow):
    def __init__( self ):
        '''Initialize the super class
        '''
        #QMainWindow.__init__(self)
        #super().__init__()
        #self.setupUi(self)
        super(MyMainWindow,self).__init__()
        uic.loadUi("pymcu_mainwindow.ui",self)
        self.MakeConnections()
        self.StackedPages.setCurrentIndex(1)

        
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
        self.browseSlot()

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
    import sys
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


