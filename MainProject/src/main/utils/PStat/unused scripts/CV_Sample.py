import sys
import toolkitpy as tkp
#from toolkitpy.toolkitcurves import *
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
from matplotlib import pyplot as plt
from mpl_point_clicker import clicker  

def initialize_pstat(pstat:tkp.PyPstat):
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
def plotCV(curve, data, ScanRate, ScanRates, ScanNumber, ScanDelay, data_frame, fig, ax,colors):
    plt.cla()
    ax.set_xlabel('E vs Eref (V)')
    ax.set_ylabel('Current (A)')
    ax.scatter(data['vf'][1:], data['im'][1:], marker = '.', label = ScanRate,color = colors[ScanNumber])
    plt.legend(loc = 'upper left')
    plt.legend(title = "Scan Rate (V/s)")
    for i in range(ScanNumber):
            ax.scatter(data_frame[i]['vf'], data_frame[i]['im'], marker = '.', label = ScanRates[i], color = colors[i])
            plt.legend(loc = 'upper left')
            plt.legend(title = "Scan Rate (V/s)")
    plt.tight_layout()
    plt.pause(0.02)
tkp.toolkitpy_init("RunPyBind")
pstat = tkp.PyPstat("PSTAT")  
initialize_pstat(pstat)
FileName = "CV_Sample" #Parent file name. Output data files will be named "file_name with x scan rate.csv"
VInit = .25 #Initial Voltage
VLimit1 = .5 #Potentiostat scans to Voltage Apex 1
V1hold = 0.0 #Hold time for first vertex (s)
VLimit2 = .25 #Potentiostat scans to Voltage Apex 2
V2hold = 0.0 #Hold time for second vertex (s)
VFinal = 0.5 #Final Voltage
Vfhold = 0.0 #Hold time for the final vertex (s)
ScanRate = 0.1 #Scan rate (V/s)
ResVal  = 0.001 #Step Size (V)
Cycles = 1 #Number of cycles per scan
NumOfScans = 10   #Total number of scans collected sequentially
Increment = 0.01 #Between each scan from NumOfScans, the ScanRate will change by Increment (V/s)
ScanDelay = 0    #Time delay between each subsequent scan. (s)
SampleTime  = ResVal/ScanRate
data_frame = dict()


"""A little bit of explanation on the r_up_dn_new 
Parameter 1: Vertex: List[float] 
    Four-element array that specifies the inital, Apex1, Apex2, and final value in volts or amperes
Parameter2: VectorScanRate: List[float]
    Three-element arrayt that specifies the inital (to apex1),apex2, and final scan rates in volts/seconds or ampere seconds
Parameter3: VectorHoldTime: list[float]
    Three-element array that specifies the hold times in seconds at Apex1, Apex2, and at the end.
Parameter 4: SampleRate: Float
    Time between data acquisition steps
Parameter 5: MaxCycles: int
    Maximum number of applied cycles
Parameter 6: CtrlMode: CTRLMODE <- Enumerator
    The potentiostats control mode
"""
    
SampleMode = 1 
fig = plt.figure()
ax = fig.gca()
number_of_colors = NumOfScans
cmap = plt.get_cmap("tab20b") # Choose a color scheme that you think looks best. Or whatever system of coloring the scans
colors = [cmap(i) for i in np.linspace(0, 1, number_of_colors)]

ScanRates = []
for ScanNumber in range(NumOfScans):
    estimated_time = (int(abs(VLimit1 - VInit) / ResVal + 0.5) + int(abs(V1hold/SampleTime)+0.5) + Cycles*(int(abs((VLimit2 - VLimit1) / ResVal) + 0.5) + int((V2hold / SampleTime) + 0.5)) + int(abs((VFinal - VLimit2) / ResVal) + 0.5) + int((Vfhold / SampleTime) + 0.5))*SampleTime
    print("This scan should take {} seconds with a {} second delay between cycles".format(int(estimated_time +.5), ScanDelay)) #This is just so you know that your loop is or is not infinite
    Signal = pstat.signal_r_up_dn_new([VInit, VLimit1, VLimit2, VFinal], [ScanRate, ScanRate, ScanRate], 
                                    [V1hold,V2hold,Vfhold],SampleTime,Cycles,SampleMode)
    pstat.set_signal_r_up_dn(Signal)
    pstat.init_signal()
    pstat.set_cell(True)
    MaxSize = 100000
    CV = tkp.RCVWrapper(pstat,MaxSize)
    CV.run(True)
    fileName = FileName + ' with ' +str(ScanRate) + ' scan rate.csv'
    while CV.running():
        time.sleep(0.010)
        data = CV.acq_data()
        np.savetxt(fileName, data, delimiter = '\t', header = 'IERange, Overload, Time, Vsig, Ach, Im, Vf, Vu, Cycle, Temp, StopTest', fmt='%s')
        plotCV(CV, data, ScanRate,ScanRates, ScanNumber, ScanDelay, data_frame,fig, ax,colors)
        
    data_frame[ScanNumber] = data #data is added to the dictionary
    ScanRates.append(ScanRate) #the ScanRate used for data collection is added to a list
    ScanRate = ScanRate + Increment
    SampleTime  = ResVal/ScanRate 
    pstat.set_cell (True) #cell is turned off to prepare for the next interation of the loop
    time.sleep(ScanDelay) #Scan delay between CV interations as determined by user parameter input
    print("One loop done") #Another print so that you know you are moving along in your code
print("All done")     
    