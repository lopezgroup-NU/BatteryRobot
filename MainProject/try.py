
from north_c9 import NorthC9


#-37,99,75 (position 1) changed default vel
#-221,22,124 (position clamp)

c9 = NorthC9("A")

    
c9.home_robot()
c9.home_carousel()
c9.home_pump(0)
c9.set_pump_speed(0,0)

c9.move_xyz(-37,99,200)
c9.move_xyz(-37,99,75)
c9.close_gripper()
c9.move_xyz(-37,99,200)
c9.move_xyz(-221,22,200)
c9.move_xyz(-221,22,124)
c9.close_clamp()
c9.delay(1)
c9.uncap()
c9.move_xyz(-221,22,200)
c9.move_xyz(-37,99,200)
c9.move_carousel(69,60)

for i in range(1,10):
    c9.set_pump_valve(0,1)
    c9.move_pump(0,2000)
    c9.set_pump_valve(0,0)
    c9.move_pump(0,5)

c9.move_carousel(0,0)
c9.move_xyz(-221,22,200)
c9.move_xyz(-221,22,125)
c9.cap()
c9.open_clamp()
c9.move_xyz(-221,22,200)
c9.move_xyz(-37,99,200)
c9.move_xyz(-37,99,75)
c9.open_gripper()
c9.move_xyz(-37,99,200)
c9.move_xyz(0,150,250)

