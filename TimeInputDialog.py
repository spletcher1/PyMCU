from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import *
from PyQt6.QtWidgets import *
from PyQt6.QtGui import *

class DateDialog(QDialog):
    """Touch-friendly date and time picker: tap a day on the calendar, then use the large
    - and + buttons for the hour and minute (hold to repeat). Seconds are set to zero."""

    def __init__(self, parent = None):
        super(DateDialog, self).__init__(parent)
        self.setWindowTitle("Set Date and Time")
        now = QDateTime.currentDateTime()
        self.hour = now.time().hour()
        self.minute = now.time().minute()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # The chosen date and time in words, so it can be checked at a glance.
        self.summary = QLabel()
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.summary.setFont(QFont('Arial', 18, QFont.Weight.Bold))
        layout.addWidget(self.summary)

        pickers = QHBoxLayout()
        pickers.setSpacing(20)
        layout.addLayout(pickers, 1)

        self.calendar = QCalendarWidget()
        self.calendar.setFont(QFont('Arial', 14))
        self.calendar.setGridVisible(True)
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.calendar.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.calendar.setSelectedDate(now.date())
        self.calendar.selectionChanged.connect(self.UpdateSummary)
        # Month arrows big enough to tap.
        for name in ("qt_calendar_prevmonth","qt_calendar_nextmonth"):
            arrow = self.calendar.findChild(QToolButton, name)
            if arrow is not None:
                arrow.setIconSize(QSize(32,32))
                arrow.setMinimumSize(48,40)
        pickers.addWidget(self.calendar, 3)

        time = QGridLayout()
        time.setVerticalSpacing(6)
        self.hourLabel = self._AddTimeColumn(time, 0, "Hour", self.ChangeHour)
        colon = QLabel(":")
        colon.setFont(QFont('Arial', 40, QFont.Weight.Bold))
        colon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time.addWidget(colon, 2, 1)
        self.minuteLabel = self._AddTimeColumn(time, 2, "Minute", self.ChangeMinute)
        timeColumn = QVBoxLayout()
        timeColumn.addStretch(1)
        timeColumn.addLayout(time)
        timeColumn.addStretch(1)
        pickers.addLayout(timeColumn, 2)

        buttons = QHBoxLayout()
        cancel = self._BigButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = self._BigButton("Set Time")
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

        self.UpdateSummary()

    def _BigButton(self, text, width=160):
        button = QPushButton(text)
        button.setFont(QFont('Arial', 16, QFont.Weight.Bold))
        button.setMinimumSize(width, 56)
        button.setAutoDefault(False)
        return button

    def _AddTimeColumn(self, grid, column, title, change):
        caption = QLabel(title)
        caption.setFont(QFont('Arial', 12))
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(caption, 0, column)
        for row, (text, step) in ((1, ("+", 1)), (3, ("−", -1))):
            button = self._BigButton(text, 96)
            button.setFont(QFont('Arial', 24, QFont.Weight.Bold))
            # Holding a button keeps stepping, so large changes don't need many taps.
            button.setAutoRepeat(True)
            button.setAutoRepeatDelay(400)
            button.setAutoRepeatInterval(120)
            button.clicked.connect(lambda checked=False, s=step: change(s))
            grid.addWidget(button, row, column)
        value = QLabel()
        value.setFont(QFont('Arial', 40, QFont.Weight.Bold))
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(value, 2, column)
        return value

    def ChangeHour(self, step):
        self.hour = (self.hour + step) % 24
        self.UpdateSummary()

    def ChangeMinute(self, step):
        self.minute = (self.minute + step) % 60
        self.UpdateSummary()

    def UpdateSummary(self):
        self.hourLabel.setText("{:02d}".format(self.hour))
        self.minuteLabel.setText("{:02d}".format(self.minute))
        self.summary.setText(self.dateTime().toString("dddd, MMMM d, yyyy   HH:mm"))

    # get current date and time from the dialog
    def dateTime(self):
        return QDateTime(self.calendar.selectedDate(), QTime(self.hour, self.minute, 0))

    # static method to create the dialog and return (date, time, accepted)
    @staticmethod
    def getDateTime(parent = None):
        dialog = DateDialog(parent)
        dialog.setWindowFlags(parent.windowFlags() & ~QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        # Nearly fill the touchscreen (800x480 on the 7" display).
        screen = parent.screen().availableGeometry()
        dialog.resize(min(760, screen.width()-40), min(440, screen.height()-40))
        result = dialog.exec()
        date = dialog.dateTime()
        # Seconds since the epoch, or 0 if cancelled.
        if result==QtWidgets.QDialog.DialogCode.Accepted:
            return(date.toSecsSinceEpoch())
        else:
            return 0
