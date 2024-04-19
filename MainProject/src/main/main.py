from BatteryRobotUtils import BatteryRobot
from PowderShakerUtils import PowderShaker
from Locator import *
from powder_protocols import *
import time, sys

rob = BatteryRobot('A', network_serial='AU06EZ1P')
t2 = BatteryRobot('B', network = rob.network)

rob.home_robot(wait=False)
rob.home_carousel()
rob.home_pump(3)
rob.set_pump_valve(3,0)
# rob.close_gripper()
# rob.get_vial_from_rack()
# add pumps/anything to module before connecting
rob.dispense_powder_and_scale()
