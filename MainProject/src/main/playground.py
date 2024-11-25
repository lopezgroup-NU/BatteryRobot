import sys

paths = ['C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages','C:\\Users\\llf1362\\AppData\\Roaming\\Python\\Python37\\site-packages','C:\\Users\\llf1362\\Documents\\NorthIDE\\lib','C:\\Users\\llf1362\\Documents\\NorthIDE\\python37.zip','C:\\Users\\llf1362\\Documents\\NorthIDE\\DLLs','C:\\Users\\llf1362\\Documents\\NorthIDE','C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\tkintertable-1.3.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\future-0.18.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\ftdi_serial-0.1.9-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\ftd2xx-1.1.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pypiwin32-223-py3.7.egg','C:\\Users\\llf1362\\Desktop\\BatteryRobot\\MainProject\\src\\main\\utils\\PStat','C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pywin32-227-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pmw-2.0.1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyopengl-3.1.5-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyopengl_accelerate-3.1.5-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyopengltk-0.0.3-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pywavefront-1.3.2-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\numpy-1.18.4-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyglm-1.2.0-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\scikit_learn-0.23.1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\threadpoolctl-2.1.0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\scipy-1.5.0rc1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\joblib-0.15.1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\scikit_optimize-0.8.dev0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyaml-20.4.0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyyaml-5.3.1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\matplotlib-3.2.1-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\python_dateutil-2.8.1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\pyparsing-3.0.0a1-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\kiwisolver-1.2.0-py3.7-win32.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\cycler-0.10.0-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\inputs-0.5-py3.7.egg', 'C:\\Users\\llf1362\\Documents\\NorthIDE\\lib\\site-packages\\keyboard-0.13.5-py3.7.egg','C:\\Users\\llf1362\\Documents\\NorthIDE\\Lib\\site-packages']
for i in paths:
    sys.path.append(i)

from utils import BatteryRobot,PowderShaker,T8

from Locator import *
from config import powder_protocols, SourceRack
from utils.PStat.geis import *
from utils.PStat.cv import *
from temper_windows import TemperWindows
import numpy as np
rob = BatteryRobot('A', network_serial='AU06EZ1P', home = False)
t8 = T8('B', network = rob.network) # heat water vial 

# rob.move_carousel(0,0)
#temperature sensor 
temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
temperature = temper.get_temperature()
print(temperature)

#rob.move_electrolyte(True)

#needle alignment rob.move_carousel(33,80) #70 for mid
rob.set_output(6, True) #means 3 electrode
rob.set_output(7, True)
rob.set_output(8, True)

#do mapping for al grids A1, A2 etc
rob.map_water_source(csv_path = "config/water_sources.csv")
viscous = 0
fifty = 1 # pos for nacl with 50000 * 10^-6 s/cm
test_sols = [2,3,4,5,7,8,9]
waters = list(range(10,24))
#2000 = .5ml
def draw_viscous():
    rob.move_vial(rack_disp_official[viscous], vial_carousel)
    rob.goto_safe(safe_zone)
    rob.draw_to_sensor(viscous, length = 1300, viscous = True, special = True)
    rob.move_electrolyte(n=1, viscous = True)
        
def draw_test(index, test_name, special, slow = True):
    rob.move_vial(rack_disp_official[index], vial_carousel)
    if special:
        rob.goto_safe(safe_zone)
    else:
        rob.uncap_vial_in_carousel()
    rob.draw_to_sensor(index, viscous = slow, special=special)
    run_geis(test_name)
    
def draw_test2(index, special, slow = True):
    rob.move_vial(rack_disp_official[index], vial_carousel)
    if special:
        rob.goto_safe(safe_zone)
    else:
        rob.uncap_vial_in_carousel()
    rob.draw_to_sensor(index, viscous = slow, special=special)

def draw_test3(index, test_name, special=False, slow = True):
    rob.move_vial(rack_disp_official[index], vial_carousel)
    if special:
        rob.goto_safe(safe_zone)
    else:
        rob.uncap_vial_in_carousel()
    rob.draw_to_sensor(index,second_sensor = True, viscous = slow, special=special)
    run_cv2(test_name,[[0, 2, -2, 0], [0.005, 0.005, 0.005], [0.05, 0.05, 0.05], 1, 0.1])

    
def test_three_times(index,test_name, special, slow = True):
    for i in range(3):
        draw_test(index = index, test_name = f"{test_name}_{i+1}", slow = slow, special=special)
        rob.delay(3)

def test_three_times2(index,test_name, special, slow = True):
    for i in range(3):
        draw_test3(index = index, test_name = f"{test_name}_{i+1}", slow = slow, special=special)
        rob.delay(3)
        
def test_three_times3(index,test_name, special, slow = True):
    for i in range(3):
        draw_test3(index = index, test_name = f"{test_name}_{i+1}", slow = slow, special=special)
        rob.delay(3)
        
def draw_to_sensor2(id, length = 1300, purge = False, viscous = False, light = False, special = False):
    """
    Assume open vial placed between clamps. Draws 5 pumps of electrolyte, and moves it to the second sensor
    """
    v_in = 20 #speed to draw, default to medium speed
    v_out = 0 # speed to push out air

    if purge:
        v_in, v_out = 35, 5
    elif viscous: # 60 seconds per pump
        v_in, v_out = 35, 0
    elif light:
        v_in, v_out = 1, 0        

    rob.close_clamp()
    rob.delay(.5)
    rob.reset_pump()
    current_height = rob.get_needle_height(id)
    rob.move_carousel(33, current_height)
    
    rob.pump_helper(length = length, v_in = v_in, v_out = v_out)
    rob.solution_vols[id] -= 0.4 * length/1250 #  length 1250 roughly equal to 0.4ml
        
    rob.move_carousel(0,0)
    if special:
        rob.open_clamp()
        rob.move_vial(vial_carousel, rack_disp_official[id])
    else:
        rob.cap_and_return_vial_to_rack(id)
            
    for _ in range(2):
        rob.pump_helper(length = length, v_in = v_in, v_out = v_out)
    
    rob.pump_helper(length = 1200, v_in = v_in, v_out = v_out)
    rob.reset_pump()    

def consecutive_tests():
    #draw_viscous()
    #rob.purge(waters[12], n_pumps=7, speed = 17)
    #rob.purge(waters[11], n_pumps=7, speed = 17)
    #rob.purge(waters[10], n_pumps=7, speed = 17)
    #rob.purge(waters[9], n_pumps=7, speed = 17)
    for i in range(3):
        test_three_times(index= 2, test_name = f"consecutiveTests_4purge_7pump_17speed_{i+1}", special=True, slow = True)
    rob.purge(waters[13], n_pumps=7, speed = 35)
    
    
def CV_tests():
    rob.set_output(6, True) #means 3 electrode
    rob.set_output(7, True)
    rob.set_output(8, True)
    test_three_times3(index= 0, test_name = "Test1_range7_", special=True, slow = True)
    rob.purge(waters[12], n_pumps=7, speed = 22)
    rob.purge(waters[11], n_pumps=7, speed = 22)
    rob.purge(waters[10], n_pumps=7, speed = 22)
    test_three_times3(index= 1, test_name = "Test2_range7_", special=True, slow = True)
    rob.purge(waters[9], n_pumps=7, speed = 22)
    rob.purge(waters[8], n_pumps=7, speed = 22)
    rob.purge(waters[7], n_pumps=7, speed = 22)
    test_three_times3(index= 0, test_name = "Test3_range7_", special=True, slow = True)
    rob.set_output(6, False) 
    rob.set_output(7, False)
    rob.set_output(8, False)

    
def consecutive_tests2():
    draw_viscous()
    rob.purge(waters[12], n_pumps=7, speed = 22)
    rob.purge(waters[11], n_pumps=7, speed = 22)
    rob.purge(waters[10], n_pumps=7, speed = 22)
    for i in range(3):
        test_three_times2(index= 2, test_name = f"consecutiveTests_3cell__3set_3purge_7pump_22speed_{i+1}", special=True, slow = True)
    rob.purge(waters[13], n_pumps=7, speed = 35)
    
def new_pump_test_6():
    for i in range(3):
        rob.purge(waters[i], n_pumps=7, speed = 37)
        test_three_times(index= 2, test_name = f"slowVtest_1413_{i+1}", special=True, slow = True)
        rob.purge(waters[i+4], n_pumps=7, speed = 37)
        draw_test2(index= 0, special=True, slow = True)
        rob.delay(30)
    rob.purge(waters[13], n_pumps=7, speed = 37)   
        
def new_pump_test_3():
    for i in range(1,5):
        rob.purge(waters[i], n_pumps=7-i)
        test_three_times(2, f'1413_waterTest{i}', special=True, slow = True)
        rob.purge(waters[i+4], n_pumps=7-i)
        test_three_times(1, f'50000_waterTest{i}', special=True, slow = True)
        
    rob.goto_safe(safe_zone)
    
def pre_test_purge():
    rob.purge(23)
    rob.purge(22)
    rob.purge(21)
    
def new_pump_test_4():
    for i in range(1,5):
        rob.purge(waters[i], n_pumps=6, speed = 38-i*4)
        test_three_times(2, f'1413_speedTest{i}', special=True, slow = True)
        rob.purge(waters[i+4], n_pumps=6, speed = 38-i*4)
        test_three_times(1, f'50000_speedTest{i}', special=True, slow = True)

    rob.goto_safe(safe_zone)
    
def new_pump_test_5():
    for i in range(1,5):
        rob.purge(waters[i], n_pumps=6, speed = 22-i*4)
        test_three_times(2, f'1413_speedTest2{i}', special=True, slow = True)
        rob.purge(waters[i+4], n_pumps=6, speed = 22-i*4)
        test_three_times(1, f'50000_speedTest2{i}', special=True, slow = True)

    rob.goto_safe(safe_zone)

def test():
    run_cv2('mark',[[0, 1, -1, 0], [0.1, 0.1, 0.1], [0.005, 0.005, 0.005], 1, 0.1])
    run_cv2('mark1',[[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.005, 0.005, 0.005], 1, 0.1])