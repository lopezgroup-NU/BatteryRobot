import sys
sys.path.append(r'C:\Users\ablack.GAMRY\Documents\Jupyter\Meeting\Release_10_6_23\Release')
from ToolkitCommon import *
from ToolkitCurves import *
import UniversalGraph as Graph
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
import pandas as pd                      #Used for presenting data in tables
import matplotlib.pyplot as plt          #Used to plot data
from scipy import stats                  #Used for linear regression
import csv                               #Used to export data as csv files
import ocv as ocv
import traceback                         #Used for error catching
import math
from ToolkitReadZ import *
from matplotlib import pyplot as plt     #Used for plotting
from mpl_point_clicker import clicker    #Used for manual baseline correction
import psutil
print(psutil.virtual_memory())


#LAST ONE to fix the live plotting issue you would need to only plot the new stuff every time the fact that the old data is being 
#plotted every single time that a new point is obtained is what is causing this issue. I would assume some sort of append would be needed.
#The refreshing of the plot is the issue. 
InitialFreq = 20000 #20000 #Hz; FreqInit
FinalFreq = 1 #Hz; FreqFinal
PointsPerDecade = 10 #PointDensity
ACVoltage = 10.0 #mV rms; ACAmpl
DCVoltage = 0.0 #V; vs. open circuit potential; DCAmpl
Area = 1 #cm^2
EstZ = 100 #ohms; estimated impedence (Z); ZGuess
Freq = 1000

Amplitude = 0.0001
Precision = 0.01
CyclesDelay = 1
Cycles = 1

#InitDelay
Totaltime = 10
SampleRate = 0.25

OCV_filename = 'EIS OCV'
EIS_filename = "EIS"
CellSolution = "0.05 M Na2SO4 + 0.05 H2SO4"
PlotTitle = "Nyquist Plot"
def OCDelay(pstat):
    pstat = pstat
    if Totaltime == 0:
        EOC = 0 
        return EOC
    data = ocv.RunOCV('OCVData.csv',pstat)
    OCdata = data['Vf']
    return OCdata
    
    

try:
    ToolkitPyInit("RunPyBind")
    FileName = "EIS.csv"
    pstat = PyPstat("PSTAT")
    EOC = OCDelay(pstat)
    pstat.SetCell(True)
    pstat.SetCtrlMode (PSTATMODE)
    pstat.SetIConvention(ICONVENTION.ANODIC)
    READZ = ReadZ(pstat)
    READZ.SetGain(1.0)
    READZ.SetINoise(0.0)
    READZ.SetVNoise(0.0)
    READZ.SetIENoise(0.0)
    READZ.SetZmod(EstZ)
    READZ.SetIdc(pstat.MeasureI())
    READZ.SetSpeed(READZ.SPEED_NORM)
    ACAmp = 0.015
    DCAmp = 0.0
    Freq = 1000.0
    READZ.DriftCor = False
    PDV = PointsPerDecade
    IF = abs(InitialFreq)
    FF = abs (FinalFreq)
    LogIncrement = 1.0/PDV
    if IF > FF:
        LogIncrement = -LogIncrement
    Status = READZ.Measure(Freq, ACVoltage *.001, DCVoltage)
    print(Status)
    fig = plt.figure()
    ax = fig.gca()
    testfull_list = []
    Zreal_list = []
    Zimag_list = []
    Freq_list = []
    MaxPoints = Graph.CheckEISPoints(InitialFreq, FinalFreq, PointsPerDecade)
    print(MaxPoints)
    Point = 0
    while Point < MaxPoints:
        Freq = math.pow(10.0, math.log10(InitialFreq) + Point * LogIncrement)
        Status = READZ.Measure(Freq, ACVoltage*.001,DCVoltage)
        if Status == False:
            print('Bad Value.')
            if Status == 0:
                print('empty')
                continue
            elif Status == 1:
                continue
            else:
                Point += 1
                continue
        else:
            
            Zreal,Zimag = READZ.Zreal, -1*READZ.Zimag
            Zreal_list.append(Zreal)
            Zimag_list.append(Zimag)
            Freq_list.append(Freq)
            testfull_list.append([Freq,READZ.Zreal,READZ.Zimag])
            #Graph.plotEIS(ax,fig,Zreal_list,Zimag_list,Zreal, Zimag, PlotTitle)
        Point +=1
        full_list = []
        
        data = np.array((testfull_list))
        np.savetxt(EIS_filename+ '.csv', data, delimiter = ',', header = 'Freq(Hz), Zreal (ohm), Zimag (ohm)') 
        print(Point)
        print(psutil.virtual_memory())
        time.sleep(0.010)
    print("Did we make it?")   
    pstat.SetCell (False)
except BaseException as err:
    print(err)
    raise
