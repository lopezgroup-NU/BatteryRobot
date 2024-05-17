import sys
sys.path.append('\\settings')

from BatteryRobotUtils import BatteryRobot
from PowderShakerUtils import PowderShaker
from Locator import *
from powder_protocols import *
import time
import toolkitpy as tkp

rob = BatteryRobot('A', network_serial='AU06EZ1P')
t8 = BatteryRobot('B', network = rob.network)
p2 = PowderShaker('C', network = rob.network)
# rob.home_robot(wait=False)
# z = ReadZ(5)
# z.Measure(100,10,0)

# rob.home_carousel()
#t8.enable_channel(0)
# t8.set_temp(0, 50)  # set axis 0 to 50*
#rob.spin_axis(6, 0)

#moving the microplate/lid holder DO NOT USE GOTO SAFE IF NOT BREAK
# rob.goto_safe(lidholder_holder)
# rob.close_gripper()
# rob.move_z()
# rob.open_gripper()

#t8.set_temp(0, 10)  # set temp below room temp.. non cooling

# rob.dispense_powder_and_scale(LiOAc)
# rob.home_robot(wait=False)
# rob.home_carousel()
# rob.home_pump(3)
# rob.set_pump_valve(3,0)
# # rob.close_gripper()
# # rob.get_vial_from_rack()
# # add pumps/anything to module before connecting
# rob.dispense_powder_and_scale()
