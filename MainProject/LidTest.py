
from north_c9 import NorthC9
import north_c9.n9_kinematics as n9

c9 = NorthC9("A")
c9.home_robot()
c9.home_pump(0)
c9.set_pump_valve(0,1)
c9.set_pump_valve(0,0)
c9.move_pump(0,0)


c9.move_xyz(207,-123,250)
c9.move_xyz(207,-123,174)
c9.move_xyz(207,-123,250)

c9.move_xyz(-242,198,250)
c9.move_xyz(-242,198,98)
c9.move_pump(0,2000)
c9.delay(2)
c9.set_pump_valve(0,1)
c9.delay(2)
c9.move_pump(0,0)
c9.delay(2)
c9.set_pump_valve(0,0)
c9.delay(2)
c9.move_pump(0,2000)
c9.delay(2)
c9.set_pump_valve(0,1)
c9.delay(2)
c9.move_pump(0,0)
c9.delay(2)
c9.set_pump_valve(0,0)
c9.delay(2)
c9.move_pump(0,2000)
c9.delay(2)
c9.set_pump_valve(0,1)
c9.delay(2)
c9.move_pump(0,0)
c9.delay(2)
c9.set_pump_valve(0,0)
c9.delay(2)
c9.move_pump(0,2000)
c9.delay(2) #draw finish

#well1
c9.move_xyz(-242,198,250)
c9.move_xyz(96.4,94.5,250,shoulder_preference = n9.SHOULDER_OUT)
c9.move_xyz(96.4,94.5,111.1,shoulder_preference = n9.SHOULDER_OUT)
c9.move_pump(0,0)
c9.delay(2)
c9.set_pump_valve(0,1)
c9.delay(2)
c9.move_pump(0,2000)
c9.delay(2)
c9.set_pump_valve(0,0)
c9.delay(2)
c9.move_pump(0,0)
c9.delay(2)
c9.move_xyz(96.4,94.5,250,shoulder_preference = n9.SHOULDER_OUT)

c9.move_pump(0,10)
c9.move_xyz(-242,198,250)
c9.move_xyz(-242,198,98)
c9.move_pump(0,2000)
c9.delay(2)
c9.move_xyz(-242,198,250)

#well2
c9.move_xyz(111.4,93.3,250,shoulder_preference = n9.SHOULDER_OUT)
c9.move_xyz(111.4,93.3,111.1,shoulder_preference = n9.SHOULDER_OUT)
c9.move_pump(0,0)
c9.delay(2)
c9.set_pump_valve(0,1)
c9.delay(2)
c9.move_pump(0,2000)
c9.delay(2)
c9.move_xyz(111.4,93.3,250,shoulder_preference = n9.SHOULDER_OUT)

#well3
c9.move_xyz(126.6,92.7,250,shoulder_preference = n9.SHOULDER_OUT)
c9.move_xyz(126.7,92.7,111.1,shoulder_preference = n9.SHOULDER_OUT)
c9.move_pump(0,0)
c9.delay(2)
c9.set_pump_valve(0,1)
c9.delay(2)
c9.move_pump(0,2000)
c9.delay(2)
c9.move_xyz(126.7,92.7,250,shoulder_preference = n9.SHOULDER_OUT)

#well4
c9.move_xyz(142.9,88.9,250,shoulder_preference = n9.SHOULDER_OUT)
c9.move_xyz(142.9,88.9,111.3,shoulder_preference = n9.SHOULDER_OUT)
c9.move_pump(0,0)
c9.delay(2)
c9.set_pump_valve(0,1)
c9.delay(2)
c9.move_pump(0,2000)
c9.delay(2)
c9.move_xyz(142.9,88.9,206,shoulder_preference = n9.SHOULDER_OUT)


c9.move_xyz(286,-144,206)
c9.move_xyz(286,-144,220)
c9.home_robot(0)


