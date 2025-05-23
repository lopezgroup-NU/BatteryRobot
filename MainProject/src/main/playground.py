from utils import BatteryRobot,PowderShaker,T8
from experiments import create_formulation
from Locator import *
from config import powder_protocols, SourceRack
from utils.PStat.geis import *
from utils.PStat.cv import *
from temper_windows import TemperWindows
import numpy as np
# rob = BatteryRobot('A', network_serial='AU06EZ1P', home = False)
# t8 = T8('B', network = rob.network) # heat water vial 


rob = BatteryRobot('A', network_serial='AU06EZ1P', home = True)
t8 = T8('B', network = rob.network)
p2 = PowderShaker('C', network = rob.network)
waters = list(range(10,48))
create_formulation("experiments/top_constrained_15.csv", "config/source_rack.csv")
rob.run_formulation('C:/Users/llf1362/Desktop/BatteryRobot/MainProject/src/main/experiments/formulation.csv')
#rob.run_test('C:/Users/llf1362/Desktop/BatteryRobot/MainProject/src/main/experiments/experiments.csv')