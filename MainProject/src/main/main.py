from utils import BatteryRobot,PowderShaker,T8
from Locator import *
from config import powder_protocols, SourceRack
from utils.PStat.geis import *
from utils.PStat.cv import *
from utils.PStat.ocv import *
from temper_windows import TemperWindows
import numpy as np

paths = ['C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages','C:\\Users\\llf1362\\AppData\\Roaming\\Python\\Python37\\site-packages','C:\\Users\\llf1362\\Documents\\NorthIDE\\lib','C:\\Users\\llf1362\\Documents\\NorthIDE\\python37.zip','C:\\Users\\llf1362\\Documents\\NorthIDE\\DLLs','C:\\Users\\llf1362\\Documents\\NorthIDE','C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\tkintertable-1.3.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\future-0.18.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\ftdi_serial-0.1.9-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\ftd2xx-1.1.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pypiwin32-223-py3.7.egg','C:\\Users\\llf1362\\Desktop\\BatteryRobot\\MainProject\\src\\main\\utils\\PStat','C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pywin32-227-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pmw-2.0.1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyopengl-3.1.5-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyopengl_accelerate-3.1.5-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyopengltk-0.0.3-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pywavefront-1.3.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\numpy-1.18.4-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyglm-1.2.0-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\scikit_learn-0.23.1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\threadpoolctl-2.1.0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\scipy-1.5.0rc1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\joblib-0.15.1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\scikit_optimize-0.8.dev0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyaml-20.4.0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyyaml-5.3.1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\matplotlib-3.2.1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\python_dateutil-2.8.1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyparsing-3.0.0a1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\kiwisolver-1.2.0-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\cycler-0.10.0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\inputs-0.5-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\keyboard-0.13.5-py3.7.egg','C:\\Users\\llf1362\\Documents\\NorthIDE\\Lib\\site-packages']
for i in paths:
    sys.path.append(i)

rob = BatteryRobot('A', network_serial='AU06EZ1P', home = True)
t8 = T8('B', network = rob.network)
p2 = PowderShaker('C', network = rob.network)

rob.initialize_deck("config/disp_rack.csv", "config/source_rack.csv", "config/heat_rack.csv")
waters = list(range(10,48))

rob.run_formulation('C:/Users/llf1362/Desktop/BatteryRobot/MainProject/src/main/experiments/formulation.csv')
rob.run_test('C:/Users/llf1362/Desktop/BatteryRobot/MainProject/src/main/experiments/experiments.csv')

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



