# deck mapping example

from north import NorthC9
from Locator import *

c9 = NorthC9('A', network_serial='AU06EZ1P')

#revs = 10
#pitch = 0.8 mm / rev

#screw/unscrew routine:
# c9.open_gripper()
# c9.goto_safe(e_cell_screw_left)
# c9.close_gripper()
# c9.uncap(revs = 11, pitch = 0.8)
# h = c9.get_axis_position(3)
# c9.move_z(292)
# 
# c9.goto_xy_safe(e_cell_screw_left)
# c9.move_axis(c9.Z_AXIS, h)
# c9.cap(revs = 9.5, pitch = 0.8, torque_thresh=1850)
# c9.open_gripper()
# c9.goto_safe([0, 0, 0, 0])

#powder change_routine:

# 48mm spacing in y-axis between powder rack positions

#c9.open_gripper()
#c9.move_carousel(67.5, 70)  # 67.5* from home, 70mm down from home,  powder change position
#c9.goto_safe(powder_rack[n])
#c9.close_gripper()
#c9.goto_safe(carousel_powder)
#c9.open_gripper()
#c9.goto_safe([0, 0, 0, 0])  # goto_safe, home position
