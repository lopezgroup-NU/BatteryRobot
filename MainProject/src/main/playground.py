from utils import BatteryRobot,PowderShaker,T8
from Locator import *
from powder_protocols import *
from utils.PStat.geis import *
from asp_rack import AspRack
import time
import toolkitpy as tkp
from temper_windows import TemperWindows

rob = BatteryRobot('A', network_serial='AU06EZ1P', home = True)

#temperature sensor 
temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
temperature = temper.get_temperature()
print(temperature)

#rob.move_electrolyte(True)

#needle alignment rob.move_carousel(31,70)
rob.set_output(6, True)
rob.set_output(7, True)
rob.set_output(8, True)
# rob.set_output(9, False)
# rob.set_output(10, False)

#do mapping for al grids A1, A2 etc

