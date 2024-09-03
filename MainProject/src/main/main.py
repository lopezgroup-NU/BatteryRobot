from utils import BatteryRobot,PowderShaker,T8
from Locator import *
from settings import powder_protocols, AspRack
from utils.PStat.geis import *
import time
import toolkitpy as tkp

rob = BatteryRobot('A', network_serial='AU06EZ1P')
t8 = T8('B', network = rob.network)
p2 = PowderShaker('C', network = rob.network)

#capping vials on asprack takes about 800 units of torque
#todo
# 1) bumps code
# 2) move electrolyte slow medium fast
# 3) 

# rob.set_output(7, True)
# rob.set_output(8, True)
# rob.set_output(9, True)

#moving the microplate/lid holder DO NOT USE GOTO SAFE WHEN MOVING IF NOT BREAK
# rob.goto_safe(lidholder_holder)
# rob.close_gripper()
# rob.move_z()
#rob.goto(microplateholderapproach)
#rob.goto(microplateholder)
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



