import sys
import toolkitpy as tkp
# from toolkitcommon import *
# from toolkitcurves import *
from .UniversalGraph import *
from .ocv import *
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
import pandas as pd                      #Used for presenting data in tables
import matplotlib.pyplot as plt          #Used to plot data
from scipy import stats                  #Used for linear regression
import csv                               #Used to export data as csv files
import traceback                         #Used for error catching
import math
from toolkitpy import ReadZ
from matplotlib import pyplot as plt     #Used for plotting
from mpl_point_clicker import clicker    #Used for manual baseline correction
# import psutil
# print(psutil.virtual_memory())

# def OCDelay(pstat):
#     pstat = pstat
#     if Totaltime == 0:
#         EOC = 0 
#         return EOC
#     data = RunOCV('OCVData.csv',pstat)
#     OCdata = data['Vf']
#     return OCdata

def initialize_pstat(pstat:tkp.Pstat):
    """This function changes the configuration of your pstat
    Inputs
    -------------------------------------------------------------
    pstat: Pypstat object
        The pstat that you want to change the parameters of

    """
    #These will be some of the Framework parameters
    pstat.set_ach_select(tkp.ACHSELECT_GND)
    pstat.set_ie_stability(tkp.STABILITY_NORM)
    pstat.set_ca_speed(tkp.CASPEED_NORM)
    pstat.set_ground(tkp.FLOAT)
    pstat.set_ich_range(3.0)
    pstat.set_ich_range_mode(False)
    pstat.set_ich_offset_enable(False)
    pstat.set_vch_range(10.0)
    pstat.set_vch_range_mode(True)
    pstat.set_vch_offset_enable(False)
    pstat.set_ach_range(3.0)
    pstat.set_ie_range_lower_limit(0) #For none
    pstat.set_pos_feed_enable(False)
    pstat.set_analog_out(0.0)
    pstat.set_voltage(0.0)
    pstat.set_pos_feed_resistance(0.0)

#LAST ONE to fix the live plotting issue you would need to only plot the new stuff every time the fact that the old data is being 
#plotted every single time that a new point is obtained is what is causing this issue. I would assume some sort of append would be needed.
#The refreshing of the plot is the issue. 
    
def run_poteis(
    EIS_filename,
    plot = False,
    InitialFreq = 1000000, #20000 #Hz; FreqInit
    FinalFreq = .1, #Hz; FreqFinal
    PointsPerDecade = 5, #PointDensity
    ACVoltage = 10.0, #mV rms; ACAmpl
    DCVoltage = 0.0, #V; vs. open circuit potential; DCAmpl
    Area = 1, #cm^2
    EstZ = 100, #ohms; estimated impedence (Z); ZGuess
    Freq = 1000,
    Amplitude = 0.0001,
    Precision = 0.01,
    CyclesDelay = 1,
    Cycles = 1,
    Totaltime = 10,
    SampleRate = 0.25,
    CellSolution = "0.05 M Na2SO4 + 0.05 H2SO4"
#     PlotTitle = "Nyquist Plot"
    ):
    try:
        tkp.toolkitpy_init("RunPyBind")
        pstat = tkp.Pstat("PSTAT") 
        initialize_pstat(pstat)
 
    #     EOC = OCDelay(pstat)
        pstat.set_cell(True)
        pstat.set_ctrl_mode(tkp.PSTATMODE)
        pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
        READZ = ReadZ(pstat)
        READZ.set_gain(1.0)
        READZ.set_inoise(0.0)
        READZ.set_vnoise(0.0)
        READZ.set_ienoise(0.0)
        READZ.set_zmod(EstZ)
        READZ.set_idc(pstat.measure_i())
        READZ.set_speed(READZ.SPEED_NORM)
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
        MaxPoints = CheckEISPoints(InitialFreq, FinalFreq, PointsPerDecade)
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
                Zreal,Zimag = READZ.zreal, -1*READZ.zimag
                Zreal_list.append(Zreal)
                Zimag_list.append(Zimag)
                Freq_list.append(Freq)
                testfull_list.append([Freq,Zreal,Zimag])
                # if plot:
                #     plotEIS(ax,fig,Zreal_list,Zimag_list,Zreal, Zimag, PlotTitle)
            Point +=1
            full_list = []
            
            data = np.array((testfull_list))
            np.savetxt(EIS_filename+ '.csv', data, delimiter = ',', header = 'Freq(Hz), Zreal (ohm), Zimag (ohm)') 
            print(Point)
    #         print(psutil.virtual_memory())
            time.sleep(0.010)
        print("Did we make it?")   
        pstat.set_cell(False)
    except BaseException as err:
        print(err)
        raise

if __name__ == "__main__":
    run_poteis("poteis")
