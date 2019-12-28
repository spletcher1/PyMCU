import sys
import os
import random
import matplotlib
# Make sure that we are using QT5
matplotlib.use('Qt5Agg')
from PyQt5 import QtCore, QtWidgets

import numpy as np
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

class MyDFMDataPlot(FigureCanvas):
    def __init__(self, parent=None,backcolor="lightgray", width=5, height=4, dpi=100):
        self.column1Data=[0, 0, 0, 0, 0,0]
        self.column2Data=[0, 0, 0, 0, 0,0]
        self.xlabels = ['Row 1', 'Row 2', 'Row 3', 'Row 4', 'Row 5','Row 6']      
        self.x = np.arange(len(self.xlabels))  # the label locations
        self.barwidth = 0.30  # the width of the bars
        self.fig = Figure(figsize=(width, height), dpi=dpi)        
        self.axes = self.fig.add_subplot(111)
        self.axes.grid(True)      
        self.backgroundColor=backcolor            
        self.axes.set_facecolor(self.backgroundColor)
        self.fig.patch.set_facecolor(self.backgroundColor)
        FigureCanvas.__init__(self, self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self,
                                   QtWidgets.QSizePolicy.Expanding,
                                   QtWidgets.QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.compute_initial_figure()
    """Simple canvas with a sine plot."""    
    def compute_initial_figure(self):
      
        self.axes.set_ylabel('Signal')        
        self.axes.set_xlabel('DFM Row')     
        self.axes.set_ylim(0,1000)   
        self.axes.set_xticks(self.x)
        self.axes.set_xticklabels(self.xlabels)
        self.fig.tight_layout()
        rects1 = self.axes.bar(self.x - self.barwidth/2, self.column1Data, self.barwidth, label='Col1')
        rects2 = self.axes.bar(self.x + self.barwidth/2, self.column2Data, self.barwidth, label='Col2')        
        self.autolabel(rects1)
        self.autolabel(rects2)
        #self.axes.legend()
    
    def UpdateFigure(self,DFM, isbaselined):
        self.axes.cla()
        if(isbaselined):
            self.axes.set_ylabel('Baselined Signal')        
        else:
            self.axes.set_ylabel('Signal')        
        self.axes.set_xlabel('DFM Row')     
        self.axes.set_ylim(0,1000)   
        self.axes.set_xticks(self.x)
        self.axes.set_xticklabels(self.xlabels)
        self.axes.grid(True)
        self.axes.set_facecolor(self.backgroundColor)
        self.fig.patch.set_facecolor(self.backgroundColor)
        data = DFM.GetLastAnalogData(True)
        if(data==None): return
        self.column1Data=data[::2]
        self.column2Data=data[1::2]
        rects1 = self.axes.bar(self.x - self.barwidth/2, self.column1Data, self.barwidth, label='Col1')
        rects2 = self.axes.bar(self.x + self.barwidth/2, self.column2Data, self.barwidth, label='Col2')        
        self.autolabel(rects1)
        self.autolabel(rects2)
        self.draw()
   
    def autolabel(self,rects):    
        for rect in rects:
            height = rect.get_height()
            self.axes.annotate('{}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')        














