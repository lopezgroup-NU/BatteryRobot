# spinner test

from north_c9 import NorthC9
from Locator import *

c9 = NorthC9("A", network_serial='FT5RIXT4')
t8 = NorthC9("B", network=c9.network)

#todo: fw estop 
# #init system
# def init_system():
#     c9.home_robot()
#     c9.home_carousel()
#     for temp_channel in range(8):
#         t8.disable_channel(temp_channel)
#         
# 
# #temp control
# 
# t8.set_temp(0, 50)  # set axis 0 to 50*
# t8.enable_channel()
# 
# t8.disable_channel()
# t8.set_temp(0, 10)  # set temp below room temp.. non cooling
