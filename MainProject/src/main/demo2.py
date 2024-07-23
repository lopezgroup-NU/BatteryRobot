from utils.BatteryRobotUtils import BatteryRobot
from utils.PowderShakerUtils import PowderShaker
from utils.T8Utils import T8
from Locator import *
from powder_protocols import *
import time
import toolkitpy as tkp

from utils.PStat.geis import *

rob = BatteryRobot('A', network_serial='AU06EZ1P')
rob = BatteryRobot('A', network_serial='AU06EZ1P')
rob.goto_safe(safe_zone, vel=15)
rob.goto_safe(rack_official[0])
rob.close_gripper()
rob.goto_safe(vial_carousel)
rob.close_clamp()
rob.uncap()
rob.goto_safe(safe_zone)
rob.move_carousel(33,10)
rob.delay(2)
rob.move_carousel(0,0)
rob.goto_safe(vial_carousel)
rob.cap()
rob.open_clamp()
rob.goto_safe(rack_official[0])
rob.open_gripper()
rob.goto_safe(safe_zone)