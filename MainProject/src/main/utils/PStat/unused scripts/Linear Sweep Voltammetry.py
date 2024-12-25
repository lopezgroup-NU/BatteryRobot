#LSV
import sys
import toolkitpy as tkp
#from toolkitpy.toolkitcurves import *
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
from matplotlib import pyplot as plt

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

tkp.toolkitpy_init("RunPyBind")
pstat = tkp.PyPstat("PSTAT")

""""Information on the signal_ramp_new
Parameter 1: Vinit: float
    Initial Voltage in volts
Parameter 2: Vfinal : float
    Final voltage in volts
Parameter 3: Scan rate: float
    Scan rate in volts/second or amps/second
Parameter 4: SampleRate: float 
    Time betwen data-acquisition steps
Paramter 5: Control mode: enumerator:
    The control mode there are GSTATMODE, PSTATMODE, ZRAMODE, FRAMODE, ZRAX4MODE

"""


filename = "LSV.csv"
Init_V = 0
Final_V = .5
scan_rate = .1 #V/s
step_size = .002 #V
max_current = .0003
Equil_time = 0
sample_time = step_size/scan_rate
num_points = abs(Final_V - Init_V)/step_size
signal = pstat.signal_ramp_new(Init_V, Final_V,scan_rate, sample_time, tkp.PSTATMODE)
initialize_pstat(pstat)
print("Estimated amount of time to run {}".format(num_points * sample_time))
MaxSize = 100000
IV = tkp.IVWrapper(pstat,MaxSize)
pstat.set_signal_ramp(signal)
pstat.init_signal()
pstat.set_cell(True)
IV.run(True)
fig = plt.figure()
ax = fig.gca()
plt.cla()
ax.set_xlabel('E vs Eref (V)')
ax.set_ylabel('Current (A)')
while IV.running():
    time.sleep(.01)
    data = IV.acq_data()
    np.savetxt(filename, data, delimiter = '\t', header = 'time, vf, vu, im, vsig, overload, stop_test', fmt = '%s' )
    ax.scatter(data['vf'][:], data['im'][:], color = 'b')
    plt.pause(0.02)
pstat.set_cell(False)
print("All Done")

