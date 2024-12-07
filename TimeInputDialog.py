from PyQt6 import QtCore, QtGui, QtWidgets, uic
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

class DateDialog(QDialog):
    def __init__(self, parent = None):
        super(DateDialog, self).__init__(parent)

        layout = QVBoxLayout(self)

        # nice widget for editing the date
        self.datetime = QDateTimeEdit(self)
        self.setWindowTitle("Set Date and Time")
        self.datetime.setFixedSize(500,100)
        self.datetime.setFont(QtGui.QFont('SansSerif',30))
        self.datetime.setCalendarPopup(False)
        self.datetime.setDateTime(QDateTime.currentDateTime())
        layout.addWidget(self.datetime)

        # OK and Cancel buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            Qt.Orientation.Horizontal, self)
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        

    # get current date and time from the dialog
    def dateTime(self):
        return self.datetime.dateTime()

    # static method to create the dialog and return (date, time, accepted)
    @staticmethod
    def getDateTime(parent = None):
        dialog = DateDialog(parent)
        dialog.setWindowFlags(parent.windowFlags() & ~QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)   
        result = dialog.exec()
        date = dialog.dateTime()
        if result==QtWidgets.QDialog.DialogCode.Accepted:
            return(date.toSecsSinceEpoch())
        else:
            return 0
        return (date.date(), date.time(), result == QtWidgets.QDialog.DialogCode.Accepted)

def main():
    app = QApplication([])
    date, time, ok = DateDialog.getDateTime()
    print("{} {} {}".format(date, time, ok))
    app.exec()

if __name__ == "__main__":
    main()
    