import matplotlib
matplotlib.use('QtAgg')
from PyQt6 import QtWidgets
import matplotlib.colors as mcolors

import numpy as np
# backend_qtagg uses whichever Qt binding is loaded (PyQt6 here); backend_qt5agg forces Qt5.
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

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
        self.set_axis_label_color()
        self.set_frame_color()
        size_policy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)        
        FigureCanvas.setSizePolicy(self, size_policy)
        FigureCanvas.updateGeometry(self)
        self.compute_initial_figure()
    
    def set_axis_label_color(self):
        # Check if the background color is dark
        if self.is_dark_theme(self.backgroundColor):
            self.axes.xaxis.label.set_color('white')
            self.axes.yaxis.label.set_color('white')
            self.axes.tick_params(axis='x', colors='white')
            self.axes.tick_params(axis='y', colors='white')

    def set_frame_color(self):
        # Check if the background color is dark
        if self.is_dark_theme(self.backgroundColor):
            for spine in self.axes.spines.values():
                spine.set_edgecolor('white')

    def is_dark_theme(self, color):
        # Convert color to RGB and check if it is dark
        rgb = mcolors.to_rgb(color)
        luminance = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
        return luminance < 0.5

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
        if data is None: return
        AData=data[::2]
        BData=data[1::2]             
        self.pointsA.set_ydata(AData)
        self.pointsB.set_ydata(BData)
        #self.autolabel(self.rects1)
        #self.autolabel(self.rects2)        
        self.draw()

    def UpdateYAxisRange(self,min,max):
        self.axes.set_ylim(min,max)
