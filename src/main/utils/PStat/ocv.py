import sys
sys.path.append(r'C:/Program Files (x86)/Gamry Instruments/Framework/toolkitpy')
import toolkitpy as tkp
from .UniversalGraph import *
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
import pandas as pd                      #Used for presenting data in tables
import matplotlib.pyplot as plt          #Used to plot data
from scipy import stats                  #Used for linear regression
import csv                               #Used to export data as csv files
import traceback                         #Used for error catching
import math
from matplotlib import pyplot as plt     #Used for plotting
#matplolib notebook activates QT GUI for dynamic plots
from mpl_point_clicker import clicker    #Used for manual baseline correction
def RunOCV(FileName):
    tkp.toolkitpy_init("RunPyBind")
    pstat = tkp.Pstat("PSTAT")
    pstat.set_ctrl_mode(tkp.PSTATMODE)
    curve = tkp.OcvCurve(pstat,10000)
    Time = 15
    SampleRate = 0.1
    pstat.set_cell (False)
    try:

        SampleMode = 1 
        Signal = pstat.signal_const_new(0,Time, SampleRate, tkp.PSTATMODE)
        pstat.set_signal_const(Signal)
        pstat.init_signal()
        data_frame = dict()
        data = []
        fig = plt.figure()
        ax = fig.gca()

        curve.run(True)
        while curve.running():
            data = curve.acq_data()
            np.savetxt(FileName, data, delimiter = ',', header = 'Point, Time (s), VF (V), VM (V), ACH (Amp-hour), VSIG (V), Temp (°C), Overload, Stop Test')
            plotOCV(curve, data,fig,ax)
            time.sleep(.01)
    except BaseException as err:
        #Error catching
        print(err)
        traceback.print_exception(*sys.exc_info())
        #Pstat.SetCell (CELLSTATE.OFF)
        raise
    return data

def RunOCV_lastV():
    tkp.toolkitpy_init("RunPyBind")
    pstat = tkp.Pstat("PSTAT")
    pstat.set_ctrl_mode(tkp.PSTATMODE)
    curve = tkp.OcvCurve(pstat,10000)
    Time = 15
    SampleRate = 0.1
    pstat.set_cell (False)
    try:
        Signal = pstat.signal_const_new(0,Time, SampleRate, tkp.PSTATMODE)
        pstat.set_signal_const(Signal)
        pstat.init_signal()
        data = []
        

        curve.run(True)
        while curve.running():
            data = curve.acq_data()
            time.sleep(.01)
    except BaseException as err:
        #Error catching
        print(err)
        traceback.print_exception(*sys.exc_info())
        #Pstat.SetCell (CELLSTATE.OFF)
        raise
    return data[-1][2]

if __name__ == "__main__":
    pstat = tkp.Pstat("PSTAT")
    RunOCV("ocv_out.csv", pstat)