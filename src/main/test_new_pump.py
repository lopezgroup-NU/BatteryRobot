from utils import BatteryRobot,PowderShaker,T8
from Locator import *
from settings import powder_protocols, AspRack
from utils.PStat.geis import *
import toolkitpy as tkp
from temper_windows import TemperWindows

rob = BatteryRobot('A', network_serial='AU06EZ1P', home = True)
t8 = T8('B', network = rob.network)

def pump_helper():
    rob.set_pump_speed(0, 0)
    rob.set_pump_valve(0, 0)
    rob.move_pump(0, 0)
    rob.set_pump_speed(0, 10)
    rob.set_pump_valve(0, 1)
    rob.move_pump(0,1300)
    print("time")

