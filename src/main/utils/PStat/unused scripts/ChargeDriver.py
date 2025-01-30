from Charge import charge_set
import sys
import os
sys.path.append(r'C:\Users\ablack.GAMRY\Documents\Jupyter\Supporting\Release')
from toolkitcommon import *
from toolkitcurves import *
from enumerations import *
from pathlib import Path


toolkitpy_init("RunPyBind")
pstat = PyPstat("PSTAT")#Select Pstat
driver = charge_set(pstat)
driver.set_file_name("NoSuffix")
driver.set_charge_value(0)
driver.set_stop_at1(stop_ats.NoStop)
try:
    driver.run()
finally:
    if pstat is not None:
        del pstat
        toolkitpy_close()
