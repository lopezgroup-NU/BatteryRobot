import sys
# sys.path.append(r'C:\Users\ablack.GAMRY\Documents\Jupyter\Supporting\Release')
import toolkitpy as tkp
#from toolkitcommon import *
#from toolkitcurves import *
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
tkp.toolkitpy_init("RunPyBind")
pstat = tkp.PyPstat("PSTAT")  


pstat.set_ctrl_mode (tkp.PSTATMODE)


curve = tkp.CHRONOAWrapper(pstat, 10000)
Vinit = 0.50
Tinit = 0.5
SampleRate = 0.1
Vstep1 = 0.01
Tstep1 = 5
Vstep2 = 0.02
Tstep2 = 5
SampleMode = 1 #Noise Reject
Signal = pstat.signal_d_step_new(Vinit, Tinit, Vstep1, Tstep1, Vstep2, Tstep2, SampleRate, tkp.PSTATMODE) 
pstat.set_signal_d_step(Signal)
pstat.init_signal() #Init your signal
FileName = "Test.csv"

pstat.set_cell(True)  # Turn on the cell
curve.run(True);

while curve.running():
    data = curve.acq_data()
    np.savetxt(FileName, data, delimiter = ',', header ='Time (s), Vf (V), Vu, Current (amp), Vsig (V), Ach, IERange, Overload, Temp')
    time.sleep(0.010)


print("Done")
pstat.set_cell(False)
del pstat



