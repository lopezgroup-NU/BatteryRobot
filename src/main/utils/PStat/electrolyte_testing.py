import sys
sys.path.append("../..")

import time
import multiprocessing
import toolkitpy as tkp
from utils import BatteryRobot
from cv import *
from geis import *
from poteis import *

rob = BatteryRobot('A', network_serial='AU06EZ1P') 

rob.set_output(7, True)
rob.set_output(8, True)
rob.set_output(9, True)

parameter_list = { }
parameter_list['initial_freq']= 250000.0
parameter_list['final_freq'] = 1.0 

run_geis(parameter_list)

#make sure vial is properly centered between clamps first before doing anything
#rob.close_clamp()
#rob.open_clamp()

#moves carousel so that syringe enters vial
# this position is for the new syringe position as of June 5th 2024
# rob.move_carousel(136, 70) #(rotation degrees, move down) do not go past >70

# print("drawn electrolyte") 

# rob.move_carousel(136, 0) # move syringe out of solution

# move_electrolyte(False)
# print("electrolyte at electrodes") 

#run gamry tests
#tkp.toolkitpy_init("RunPyBind")
#pstat = tkp.PyPstat("PSTAT")
#run_geis(pstat, "tests/dummy")
#run_poteis(pstat, "tests/ocv","tests/eis")

# below is just code for running robot arm and gamry tests simultaneously, to be used later    
# def rob_method():
#     rob = BatteryRobot('A', network_serial='AU06EZ1P')
#     rob.home_robot()
 
# def pstat_method():
#     tkp.toolkitpy_init("RunPyBind")
#     pstat = tkp.PyPstat("PSTAT")  
#     run_cv(pstat, "cv")
#     run_geis(pstat, "GEIS")
#     run_poteis(pstat, "ocv","eis")
#     
#     
# if __name__ == '__main__':
#     # creating processes 
# #     p1 = multiprocessing.Process(target=rob_method) 
#     p2 = multiprocessing.Process(target=pstat_method) 
# 
#     # starting processes 
# #     p1.start() 
#     p2.start() 
# 
#     # wait until processes are finished 
# #     p1.join() 
#     p2.join()
#     print("done")
#
#     running EIS: c9.set_output(n, False) n = 7,8,9
#     running CV: c9.set_output(n, True)
