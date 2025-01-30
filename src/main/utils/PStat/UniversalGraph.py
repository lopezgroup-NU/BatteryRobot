import numpy as np               #Used to store and manipulate raw data output
import time                      #Used for script time delay

import matplotlib.pyplot as plt  #Used to plot data
from scipy import stats          #Used for linear regression
import csv                       #Used to export data as csv files

import numpy as np               #Used to store and manipulate raw data output
import time                      #Used for script time delay

import matplotlib.pyplot as plt  #Used to plot data
from scipy import stats          #Used for linear regression
import csv                       #Used to export data as csv files

from matplotlib import pyplot as plt
from mpl_point_clicker import clicker
import enum
import math
from matplotlib.widgets import Button


#Graphing OCV
def plotOCV(curve,  data, fig, ax):
    '''
    Plots data in real time as it is being collected and plots previous CVs collected during this execution of the script.
    '''
    plt.cla() #clear all axes to prevent redundant plotting
    plt.title("Open Current Voltage")
    ax.set_ylabel('vf') #label axes
    ax.set_xlabel('time') #label axes
    ax.scatter(data['time'][7:], data['vf'][7:], marker ='.') #lable real-time data to be plotted
    plt.tight_layout()
    fig.canvas.draw()
def plotCA(curve, data, fig, ax):
    plt.cla() #clear all axes to prevent redundant plotting
    ax.set_xlabel('Time(S)') 
    ax.set_ylabel('Current') #label axes
    ax.scatter(data['time'][1:], data['current'][1:], marker ='.') #lable real-time data to be plotted
    plt.tight_layout()
    fig.canvas.draw()
def plotLPR(curve,data,fig,ax):
    plt.cla() #clear all axes to prevent redundant plotting
    ax.set_xlabel('Current (Amp)') 
    ax.set_ylabel('Vf (V)') #label axes
    ax.scatter(data['current'][1:], data['vf'][1:], marker ='.') #lable real-time data to be plotted
    plt.tight_layout()
    fig.canvas.draw()
def plotCV(curve, data, ScanRate, ScanRates, ScanNumber, ScanDelay, data_frame, fig, ax):
    plt.cla()
    ax.set_xlabel('E vs Eref (V)')
    ax.set_ylabel('Current (A)')
    ax.scatter(data['vf'][1:], data['im'][1:], marker = '.', label = ScanRate)
    plt.legend(loc = 'upper left')
    plt.legend(title = "Scan Rate (V/s)")
    for i in range(ScanNumber):
        print(ScanRate)
        if i == 0:
            if ScanNumber == 0:
                continue
            else:
                ax.scatter(data_frame[i]['vf'], data_frame[i]['im'], marker = '.', label = ScanRates[i])
        else:
            ax.scatter(data_frame[i]['vf'], data_frame[i]['im'], marker = '.', label = ScanRates[i])
            plt.legend(loc = 'upper left')
            plt.legend(title = "Scan Rate (V/s)")
            plt.tight_layout()
            fig.canvas.draw()
    plt.tight_layout()
    fig.canvas.draw()

def plotEIS(ax,fig,Zreal_list, Zimag_list, Zreal,Zimag, PlotTitle):
    plt.cla()
    ax.set_xlabel('Zreal (ohm)')
    ax.set_ylabel('-Zimag (ohm)')
    ax.scatter(Zreal_list,Zimag_list, marker = '.', color = 'b')
    ax.scatter(Zreal, Zimag, marker = '.', color = 'b')
    ax.axhline(y=0, color = 'k', linestyle = ':')
    plt.title(PlotTitle)
    plt.tight_layout();
    fig.canvas.draw();
#def testEis(ax,fig,zreal_list, zimag_list, zreal,zimag, plot_title):
    
def CheckEISPoints(InitialFreq, FinalFreq, PointsPerDecade):
    #Calculate the number of points for an EIS curve.
    InitLog = False
    FinalLog = False
    if abs(math.log10(InitialFreq)) == float(math.floor(abs(math.log10(InitialFreq)))):
        InitLog = True

    if abs(math.log10(FinalFreq)) == float(math.floor(abs(math.log10(FinalFreq)))):
        FinalLog = True

    if InitLog  == True and FinalLog == True:
        Factor = 0
    else:
        Factor = 1

    Result = Factor + math.floor(round( 0.5 + abs(math.log10(FinalFreq)-math.log10(InitialFreq)) * PointsPerDecade , 0))
    return Result        
# def graph_pwr_charge_const(curve, data, fig, ax):
#     plt.cla() #clear all axes to prevent redundant plotting
#     ax.set_xlabel('Time(S)') 
#     ax.set_ylabel('Voltage') #label axes
#     ax.scatter(data['time'][1:], data['vf'][1:], marker ='.') #lable real-time data to be plotted
#     ax.scatter(data['time'][1:], data['im'][1:], marker ='.') #lable real-time data to be plotted
#     plt.tight_layout();
#     fig.canvas.draw()
def graph_pwr_charge_const(curve, data, fig, ax):
    plt.cla() #clear all axes to prevent redundant plotting
    ax.set_xlabel('Time(S)') 
    ax.set_ylabel('Voltage') #label axes
    ax.scatter(data['time'][1:], data['vf'][1:], marker ='.') #lable real-time data to be plotted
    ax.scatter(data['time'][1:], data['im'][1:], marker ='.') #lable real-time data to be plotted
    plt.draw()
    

