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
        self.xlabels = [' ','Row 1', 'Row 2', 'Row 3', 'Row 4', 'Row 5','Row 6']      
        #self.xlabels = ['1A', '1B', '2A', '2B', '3A','3B','4A', '4B', '5A', '5B', '6A','6B']      
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
      
    def compute_initial_figure(self):      
        self.axes.set_ylabel('Signal')        
        self.axes.set_xlabel('DFM Row')     
        self.axes.set_ylim(0,1000)   
        self.axes.set_xticks(self.x)
        self.axes.set_xticklabels(self.xlabels)
        self.axes.grid(True)
        self.fig.tight_layout()
        self.axes.set_facecolor(self.backgroundColor)
        self.fig.patch.set_facecolor(self.backgroundColor)
        self.pointsA, = self.axes.plot([0.8,1.8,2.8,3.8,4.8,5.8],[1,2,3,4,5,6],"bo",markersize=11)
        self.pointsB, = self.axes.plot([1.2,2.2,3.2,4.2,5.2,6.2],[7,8,9,10,11,12],"ro",markersize=11)
        
        self.draw()
    def UpdateFigure(self,DFM, isbaselined):           
        data = DFM.GetLastAnalogData(True)      
        if(data==None): return
        AData=data[::2]
        BData=data[1::2]        
        self.pointsA.set_ydata(AData)
        self.pointsB.set_ydata(BData)
        #self.autolabel(self.rects1)
        #self.autolabel(self.rects2)        
        self.draw()

    def UpdateYAxisRange(self,min,max):
        self.axes.set_ylim(min,max)   
        
    def compute_initial_figureBARS(self):      
        self.axes.set_ylabel('Signal')        
        self.axes.set_xlabel('DFM Row')     
        self.axes.set_ylim(0,1000)   
        self.axes.set_xticks(self.x)
        self.axes.set_xticklabels(self.xlabels)
        self.axes.grid(True)
        self.fig.tight_layout()
        self.axes.set_facecolor(self.backgroundColor)
        self.fig.patch.set_facecolor(self.backgroundColor)
        self.rects1 = self.axes.bar(self.x - self.barwidth/2, self.column1Data, self.barwidth, label='Col1')
        self.rects2 = self.axes.bar(self.x + self.barwidth/2, self.column2Data, self.barwidth, label='Col2')        
        #self.autolabel(self.rects1)
        #self.autolabel(self.rects2)
        self.axes.legend()
   
    def UpdateFigureBARS(self,DFM, isbaselined):        
        data = DFM.GetLastAnalogData(True)
        if(data==None): return
        self.column1Data=data[::2]
        self.column2Data=data[1::2]
        [rect.set_height(h) for rect,h in zip(self.rects1,self.column1Data)]
        [rect.set_height(h) for rect,h in zip(self.rects2,self.column2Data)]
        #self.autolabel(self.rects1)
        #self.autolabel(self.rects2)
        self.draw()
    
   
    def autolabel(self,rects):    
        for rect in rects:
            height = rect.get_height()
            self.axes.annotate('{}'.format(height),
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom')        














