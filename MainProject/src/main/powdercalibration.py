from BatteryRobotUtils import BatteryRobot
from PowderShakerUtils import PowderShaker
from Locator import *
from powder_protocols import *
import time, sys

rob = BatteryRobot('A', network_serial='AU06EZ1P')
p2 = PowderShaker('C', network = rob.network)
# rob.close_clamp()
# rob.delay(1)
# rob.open_clamp()
# rob.delay(1)

# rob.move_carousel(68,77)
#best so far
# LiOAc = PowderProtocol(tol = 0.2,
#                             fast_settings = PowderSettings(
#                                 opening_deg = 40,
#                                 percent_target = 0.9,
#                                 max_growth = 3
#                                 ),
#                             med_settings = PowderSettings(
#                                 thresh = 50,
#                                 opening_deg = 35,
#                                 percent_target = 0.9,
#                                 max_growth = 1.3
#                                 ),
#                             slow_settings = PowderSettings(
#                                 thresh = 10,
#                                 opening_deg = 28,
#                                 percent_target = 0.8,
#                                 max_growth = 1.1,
#                                 amplitude = 80,
#                                 shut_valve = False
#                                 ),
#                             ultra_slow_settings = PowderSettings(
#                                 thresh = 2,
#                                 opening_deg = 27,
#                                 percent_target = 0.8,
#                                 max_growth = 1.1,
#                                 amplitude = 70,
#                                 shut_valve = False
#                                 ),
#                              scale_delay=1
#                             )

with open("dispensingpowdercalibration.txt", "a") as f:
    f.write("\nRecalibrated...\n")
    dispensed = 0
    total_time = 0
    iters = 10
    for i in range(iters): # todo make p2.clpowdispense return settings and add to txt file
        print(i)
        now = time.time()
        total = p2.cl_pow_dispense(robot = rob, mg_target = 10, protocol = LiOAc)
        dispensed += total
        end = time.time()
        f.write(f"iteration {i} dispensed: {total} time = {end-now}\n")
        total_time += (end-now)
        
    f.write(f"avg mass = {dispensed/iters} avg time taken = {total_time / iters}\n")
    f.close()