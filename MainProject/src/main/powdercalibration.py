from BatteryRobotUtils import BatteryRobot
from PowderShakerUtils import PowderShaker
from Locator import *
from powder_protocols import *
import time, sys

rob = BatteryRobot('A', network_serial='AU06EZ1P')
p2 = PowderShaker('C', network = rob.network)



with open("dispensingpowdercalibration.txt", "a") as f:
    f.write("\nRecalibrated...\n")
    dispensed = 0
    total_time = 0
    iters = 1
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