#Galv EIS
import sys
import toolkitpy as tkp
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
import math
import matplotlib
matplotlib.use('TkAgg')
from toolkitpy.toolkitreadz import ReadZ
from toolkitpy.toolkitreadzae import ReadZAE
import matplotlib.pyplot as plt          #Used to plot data
tkp.toolkitpy_init("RunPyBind")
pstat = tkp.PyPstat("PSTAT")  
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
def initialize_pstat(pstat):
     #These settings 494 Galvanostatic EIS in the explain scripts. 
     pstat.set_cell(False)          
     pstat.set_ach_select(tkp.ACHSELECT_GND)
     pstat.set_ie_stability(tkp.STABILITY_FAST)
     pstat.set_ca_speed(tkp.CASPEED_NORM)
     pstat.set_ground(tkp.FLOAT)
     pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
     pstat.set_ich_range(3.0)
     pstat.set_ich_range_mode(False)
     pstat.set_ich_filter(3.0)
     pstat.set_vch_range(3.0)
     pstat.set_ich_range_mode(False)
     pstat.set_vch_range_mode(False)
     pstat.set_ich_offset_enable(True)
     pstat.set_vch_offset_enable(True)
     pstat.set_vch_filter(2.50)
     pstat.set_ach_range(3.0)
     pstat.set_ie_range(0.03)
     pstat.set_ie_range_mode(False)
     pstat.set_ie_range_lower_limit(0)
     pstat.set_analog_out(0.0)
     pstat.set_pos_feed_enable(False)
     pstat.set_irupt_mode(tkp.IRUPTOFF)
def readz_setup(readz,pstat):
     #These parameters are gathered starting from line ~302 in Galvanostatic EIS.exp
    #------------------------------------------------------------------------------------
    readz.set_gain(1.0)
    readz.set_inoise(0.0)
    readz.set_vnoise(0.0)
    readz.set_ie_noise(0.0)
    readz.set_zmod(estimated_z)
    readz.set_idc(dc_current)
    IERange = pstat.test_ie_range(abs(dc_current))
    Rm = pstat.ie_resistor(IERange)
    Sdc = Rm*dc_current
    Sac = Rm*ac_current
    #----------------------------------------------------------------------
    #readz.set_speed(0) #Fast
    readz.set_speed(1) #Normal
    #readz.set_speed(2) #low Noise
    #readz.set_drift_cor(True)
    readz.set_drift_cor(False)
    pstat.set_ctrl_mode(tkp.GSTATMODE)
    pstat.set_ie_range(IERange)
    pstat.set_voltage(Sdc)
    readz.set_vdc(pstat.measure_v())

#Parameters
#------------------------------------------------------------------
inital_freq = 100000
final_freq = 1
ac_current = .0001
dc_current = 0
estimated_z = 100
PDV = 10 #Points per decade
file_name = "GEIS" #There is no check for suffixes therefore this file should not have the .csv at the end
#-----------------------------------------------------------
FF = abs(final_freq)
IF = abs(inital_freq)
F_lim_lower = pstat.freq_limit_lower()
F_lim_upper = pstat.freq_limit_upper()
if(IF > F_lim_upper):
    print("Inital frequency exceeds upper frequency limit")
    IF = F_lim_upper
if(FF > F_lim_upper):
    FF = F_lim_upper
    print("Final frequency exceeds upper frequency limit")
if(IF < F_lim_lower):
    IF = F_lim_lower
    print("Inital frequency exceeds lower frequency limit")
if(FF < F_lim_lower):
    FF = F_lim_lower
    print("Final frequency exceeds lower frequency limit")
inital_freq = IF
final_freq = FF 
initialize_pstat(pstat)
readz = ReadZ(pstat)
readz_setup(readz,pstat)

Logincrement = 1.0/PDV
if IF > FF:
    Logincrement = -Logincrement
MaxPoints = CheckEISPoints(inital_freq, final_freq, PointsPerDecade=PDV)
zreal_list = []
testfull_list = []
freq_list = []
zimag_list = []
zmod_list = []
ie_range_list = []
zphz_list = []
fig, (ax, ax3) = plt.subplots(1,2, figsize = (12,10))
ax.set_xlabel("Frequency")
ax.set_ylabel("Zmod")
ax2 = ax.twinx()
ax2.set_ylabel("Phase")
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_ylim(100,1E6 )
ax2.set_ylim(-90,90)
ax.set_title("Bode")
ax3.set_title("Nyquist")
ax3.set_xlabel("Z real (ohm)")
ax3.set_ylabel("Z imiaginary (Ohm)")
added = True
current_points = 0
pstat.set_cell(tkp.CELL_ON)
while current_points < MaxPoints:
    freq = math.pow(10.0, math.log10(inital_freq) + current_points * Logincrement)
    status = readz.Measure(freq, ac_current,dc_current)
    
    if status == False:
        print('Bad Value')
        if(status == 0):
                press == True
        elif(status == 1):
                continue
        else:
                current_points += 1
                continue
    else:
        zreal,zimag = readz.zreal, -1*readz.zimag
        zmod = readz.zmod
        zphz = readz.zphz
        zmod_list.append(zmod)
        zphz_list.append(zphz)
        current_range = pstat.ie_range()
        zreal_list.append(zreal)
        zimag_list.append(zimag)
        freq_list.append(freq)
        ie_range_list.append(current_range)
        testfull_list.append([freq,zreal,zimag,current_range])
        ax.scatter(freq_list,zmod_list, marker = '.', color = 'b',label = 'Zmod')
        ax2.scatter(freq_list, zphz_list,marker = '.', color = 'r', label = 'zphase')
        ax3.scatter(zreal_list, zimag_list, marker = '.', color = 'b') 
        if added:
             ax.legend()
             ax2.legend(loc = 'upper left' )
             added = False
        ax.axhline(y=0, color = 'k', linestyle = ':')
        plt.pause(0.05)
    current_points +=1
    full_list = []
    data = np.array(testfull_list)
    np.savetxt(file_name + '.csv', data,delimiter = ',', header = 'Freq(Hz), Zreal (ohm), Zimag (ohm), IE Range' )
    time.sleep(.010)
rawdata = readz.fra_curve.full_acq_data() 
print(rawdata)
np.savetxt(file_name + 'raw.csv', rawdata, delimiter = ',')  
pstat.set_cell(False)
del pstat
tkp.toolkitpy_close()