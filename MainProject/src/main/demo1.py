from utils import BatteryRobot,PowderShaker,T8
from Locator import *
from powder_protocols import *
from utils.PStat.geis import *
from asp_rack import AspRack
import time
import toolkitpy as tkp
from temper_windows import TemperWindows

rob = BatteryRobot('A', network_serial='AU06EZ1P', home = True)
t8 = T8('B', network = rob.network)

vial_map = "water1 water2 a b c d e f g h i j k l m n o p q r s t u v"
vol_map = "7 8 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0"
rob.map_asp_rack(vial_map, vol_map)

# 1M
pow_data = rob.dispense_powder_and_scale(LiOAc, 0, 1, collect = True, ret = False)
# 
# 
rob.dispense_liquid_vol(0, "water1", 3, collect = False, ret = False)
rob.move_vial(vial_carousel, heatplate_official[0])
t8.set_temp(0,70)
t8.enable_channel(0)
rob.spin_axis(6,800)

# rob.move_vial(heatplate_official[0], vial_carousel)
# rob.move_electrolyte()


#5M
# pow_data = rob.dispense_powder_and_scale(LiOAc, 1, 1980, collect = True, ret = False)
# rob.dispense_liquid_and_scale(1, "water2", 6, collect = False, ret = False)
# rob.move_vial(vial_carousel, heatplate_official[1])
# stir, heat
# rob.move_vial(heatplate_official[1], vial_carousel)
# rob.move_electrolyte()