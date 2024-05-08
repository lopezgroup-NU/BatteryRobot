import sys
sys.path.append('\\settings')

from BatteryRobotUtils import BatteryRobot
from PowderShakerUtils import PowderShaker
from Locator import *
from powder_protocols import *
import time

rob = BatteryRobot('A', network_serial='AU06EZ1P')
t2 = BatteryRobot('B', network = rob.network)
p2 = PowderShaker('C', network = rob.network)
rob.home_pump(3)
rob.set_pump_valve(3,0)

rob.home_robot()
rob.home_carousel()

rob.open_clamp()
rob.open_gripper()
rob.zero_scale()
            
rob.get_vial_from_rack(0, rack_dispense_official)
rob.goto_safe(vial_carousel)
rob.close_clamp()
rob.delay(.7)
            
rob.uncap()
rob.goto_safe(safe_zone)
rob.open_clamp()
            
rob.move_carousel(68, 77) # carousel moves 68 degrees, 75 mm down
dispensed = p2.cl_pow_dispense(robot = rob, mg_target = 5, protocol = LiOAc)
rob.delay(1)
rob.move_carousel(0,0)
       
# for i in range(3):
#     rob.dispense_liquid_and_scale(n_vials = 1)
volume = 2
rob.get_pipette(0)
for i in range(3):
    rob.delay(.5)
    rob.goto_safe(rack_pipette_aspirate[0])
    rob.delay(1)
    rob.aspirate_ml(3,volume-1)
    rob.delay(.5)
    rob.goto_safe(carousel_dispense)
    rob.delay(1)
    rob.zero_scale()
    rob.delay(1)
    rob.dispense_ml(3,volume-1)
    rob.delay(.5)
    rob.goto_safe(rack_pipette_aspirate[1])
    rob.aspirate_ml(3,volume-1)
    rob.delay(.5)
    rob.goto_safe(carousel_dispense)
    rob.dispense_ml(3,volume-1)
    rob.delay(.5)

rob.remove_pipette()
rob.close_clamp()
rob.goto_safe(carousel_cap_approach)
rob.cap()
rob.open_clamp()
rob.goto_safe(heatplate_official[2])
rob.open_gripper()
rob.goto_safe(safe_zone)
print("heating up stuff")
time.sleep(5)
rob.get_vial_from_rack(2, heatplate_official)
rob.goto_safe(vial_carousel)
rob.close_clamp()
rob.delay(.7)
rob.uncap()
rob.goto_safe(safe_zone)
rob.move_carousel(315,70)







