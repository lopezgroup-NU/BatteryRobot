
from north_c9 import NorthC9
c9 = NorthC9("A")
c9.home_pump(0)
#c9.set_pump_speed(0,0)

for i in range(1,60):
    c9.set_pump_valve(0,1)
    c9.move_pump(0,2000)
    c9.set_pump_valve(0,0)
    c9.move_pump(0,5)
#c9.move_xyz(80,80,75)
#c9.move_xyz(40,280,50)
