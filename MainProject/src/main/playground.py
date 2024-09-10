from utils import BatteryRobot,PowderShaker,T8
from Locator import *
from settings import powder_protocols, AspRack
from utils.PStat.geis import *
import time
import toolkitpy as tkp
from temper_windows import TemperWindows

rob = BatteryRobot('A', network_serial='AU06EZ1P', home = True)
t8 = T8('B', network = rob.network) # heat water vial 

# rob.move_carousel(0,0)
#temperature sensor 
temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
temperature = temper.get_temperature()
print(temperature)

#rob.move_electrolyte(True)

#needle alignment rob.move_carousel(32,80) #70 for mid
#rob.set_output(6, True)
#rob.set_output(7, True)
#rob.set_output(8, True)
# rob.set_output(9, False)
# rob.set_output(10, False)

#do mapping for al grids A1, A2 etc
rob.map_water_source(csv_path = "settings/water_sources.csv")
test_sol= 0
viscous = 1
needle_1_test, needle_2_test = 7, 8

def draw_viscous():
    rob.move_vial(rack_disp_official[viscous], vial_carousel)
    rob.uncap_vial_in_carousel()  
    rob.draw_to_sensor(viscous, viscous=True)
    rob.move_carousel(0, 0)
    rob.delay(60)
    rob.move_electrolyte(n = 3, viscous = True)
    rob.delay(60)
    rob.move_electrolyte(n = 5, viscous = True)

def draw_test(index = test_sol):
    rob.move_vial(rack_disp_official[index], vial_carousel)
    rob.uncap_vial_in_carousel()  
    rob.draw_to_sensor(index)
    rob.move_carousel(0, 0)

def rinse_needle_1(): #move in and out of water
    t8.set_temp(0,70)
    rob.delay(600)
    rob.move_vial(heatplate_official[0], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.move_carousel(32,85)
    rob.delay(1200)
    rob.cap_and_return_vial_to_rack(0, heatplate_official)
    t8.set_temp(0,50)
    rob.move_vial(rack_disp_official[11], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.move_carousel(32,85)
    rob.delay(300)
    rob.cap_and_return_vial_to_rack(11)

def rinse_needle_2():
    rob.move_vial(rack_disp_official[11], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.move_carousel(32,85)
    rob.delay(3600)
    rob.cap_and_return_vial_to_rack(11)
    
def test_purge_protocols():
    #control
    draw_test()
    run_geis("control")

    '''
    sept 10 tests
    #needle washing tests 
    1)hotter water leave for 20 mins, 5 min dip in cold water
    slow purge
    test
    2)leave for 1 hr cold water
    slow purge
    test

    #tests
    wash needle each time
    hotter water leave for 20 mins, 5 min dip in cold water
    1) heat then purge. purge_draw_measure 3x. 
    2) 2x purge. purge_draw_measure 3x. 
    3) slow purge with 20 pumps. reach sensors - super slow. then medium
    4) sendit with cold water.

    '''
    #needle washing #1
    draw_viscous()
    rinse_needle_1()
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2
    draw_test(index = needle_1_test)
    run_geis("needle_washing_1_soak_hotsoakandcool")

    #needle washing #2
    draw_viscous()
    rinse_needle_2()
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2
    draw_test(index = needle_2_test)
    run_geis("needle_washing_2_soak_1hr")

    #cleaning tests

    #test 1
    draw_viscous()
    rinse_needle_1()
    rob.move_vial(heatplate_official[1], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 20, light= True)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(1, heatplate_official)
    rob.move_electrolyte(n = 10, light = True)
    
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos, speed=13)
    rob.water_sources[i][1] -= 4.2
    draw_test()
    run_geis("heat_then_purge_draw_measure_1")
    draw_test()
    run_geis("heat_then_purge_draw_measure_2")
    draw_test()
    run_geis("heat_then_purge_draw_measure_3")

    #test 2
    draw_viscous()
    rinse_needle_1()
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2

    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2

    draw_test()
    run_geis("2x_purge_draw_measure_1")
    draw_test()
    run_geis("2x_purge_draw_measure_2")
    draw_test()
    run_geis("2x_purge_draw_measure_3")

    #test 3
    draw_viscous()
    rinse_needle_1()
    i, pos = rob.next_water_source(4.2)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 20, viscous=True)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 2
    rob.move_electrolyte(n = 20, extra_slow = True)
    draw_test()
    run_geis("slow_then_super_slow_through_sensors")

    #test 4
    draw_viscous()
    rinse_needle_1()
    i, pos = rob.next_water_source(6)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 60)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 6
    rob.move_electrolyte(n = 60)
    draw_test()
    run_geis("SENDITMEDIUM")

    """
    #sept 9 retests with clean NaCl
    #test 1
    draw_viscous()
    rinse_needle_1()
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2
    
    rob.move_vial(rack_disp_official[test_sol], vial_carousel)
    rob.uncap_vial_in_carousel()  
    rob.draw_to_sensor()
    run_geis("res/purge_draw_measure_3x_1")
    rob.draw_to_sensor()
    run_geis("res/purge_draw_measure_3x_2")
    rob.draw_to_sensor()
    run_geis("res/purge_draw_measure_3x_3")
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(test_sol)

    #test 2
    draw_viscous()
    rinse_needle_1()
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2 

    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2 

    draw_test()
    run_geis("res/2x_purge_slow")   

    #test 3
    draw_viscous()
    rinse_needle_1()
    rob.move_vial(heatplate_official[1], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 20, light= True)
    rob.move_carousel(0, 0)
    rob.move_electrolyte(n = 10, light = True)
    rob.cap_and_return_vial_to_rack(1, heatplate_official)
    
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos, speed=13)
    rob.water_sources[i][1] -= 4.2
    draw_test()
    run_geis("res/heat_then_purge")   
    """
    # # sept 6 tests for G to run in the day. comment out sept 4 tests first!

    # #test 1
    # #SENDD ITTT (fast)

    # draw_viscous()
    # i, pos = rob.next_water_source(6)
    # rob.move_vial(rack_disp_official[pos], vial_carousel)
    # rob.uncap_vial_in_carousel()
    # rob.close_clamp()
    # rob.open_clamp()
    # rob.move_carousel(32,85)
    # rob.move_electrolyte(n = 60, light= True)
    # rob.move_carousel(0, 0)
    # rob.cap_and_return_vial_to_rack(pos)
    # rob.water_sources[i][1] -= 6
    # rob.move_electrolyte(n = 60, light= True)
    # draw_test()
    # run_geis("res/SENDITFAST")

    # #test 2
    # #SENDD ITTT (medium)

    # draw_viscous()
    # i, pos = rob.next_water_source(6)
    # rob.move_vial(rack_disp_official[pos], vial_carousel)
    # rob.uncap_vial_in_carousel()
    # rob.close_clamp()
    # rob.open_clamp()
    # rob.move_carousel(32,85)
    # rob.move_electrolyte(n = 60)
    # rob.move_carousel(0, 0)
    # rob.cap_and_return_vial_to_rack(pos)
    # rob.water_sources[i][1] -= 6
    # rob.move_electrolyte(n = 60)
    # draw_test()
    # run_geis("res/SENDITMEDIUM")

    # #test 3
    # #SENDITT FAST 70 deg water
    # draw_viscous()
    # rob.move_vial(heatplate_official[1], vial_carousel)
    # rob.uncap_vial_in_carousel()
    # rob.close_clamp()
    # rob.open_clamp()
    # rob.move_carousel(32,85)
    # rob.move_electrolyte(n = 60, light= True)
    # rob.move_carousel(0, 0)
    # rob.cap_and_return_vial_to_rack(1, heatplate_official)
    # rob.move_electrolyte(n = 60, light= True)
    # run_geis("res/SENDITEXTRAHOT")        

    """
    #sept 4 purge tests
        
    #test 1 shake fast hot
    draw_viscous() 
    rob.move_vial(heatplate_official[2], vial_carousel) 
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 12)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(2, heatplate_official) 
    for _ in range(10):
        rob.shake(num_shakes = 150, fast = True)
        rob.delay(1)
        rob.move_electrolyte(n=1)
        rob.delay(1)
    draw_test()
    run_geis("res/shake_fast_1500x_hot")    #it broke somehow during the Electrochemistry

    #test 2 hot purge
    draw_viscous()
    rob.move_vial(heatplate_official[2], rack_disp_official[17])
    rob.purge(17)
    rob.move_vial(rack_disp_official[17], heatplate_official[2])
    draw_test()
    run_geis("res/purge_hot")
    
    #test 3 purge_draw_and_measure_3x
    draw_viscous()
    
    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2
    
    rob.move_vial(rack_disp_official[test_sol], vial_carousel)
    rob.uncap_vial_in_carousel()  
    rob.draw_to_sensor()
    run_geis("res/purge_draw_measure_3x_1")
    rob.draw_to_sensor()
    run_geis("res/purge_draw_measure_3x_2")
    rob.draw_to_sensor()
    run_geis("res/purge_draw_measure_3x_3")
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(test_sol)
    
    #test 4 super slow
    draw_viscous()
    
    i, pos = rob.next_water_source(1)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 10)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 1.2
    rob.move_electrolyte(n = 2)
    rob.move_electrolyte(n = 10, extra_slow = True)
    rob.move_electrolyte(n = 10)
    draw_test()
    run_geis("res/super_slow")
    
    #test 5 water and air
    draw_viscous()
    
    i, pos = rob.next_water_source(2)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    for _ in range(10):
        rob.move_carousel(32,85)
        rob.move_electrolyte(n = 1)
        rob.move_carousel(0, 0)
        rob.move_electrolyte(n = 1)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 2
    rob.move_electrolyte(n = 12)
    draw_test()
    run_geis("res/water_and_air_10x")

    #test 6 wash with electrolyte 
    draw_viscous()
    
    for i in range(4):
        draw_test()
        run_geis(f"res/wash_with_electrolyte_4x_{i}")
    """
    
    #sept 3 purge tests
        
    #test 1 10 shakes - length 1 - 10 times - slow
#     draw_viscous()
#     i, pos = rob.next_water_source(1.2)
#     rob.move_vial(rack_disp_official[pos], vial_carousel)
#     rob.uncap_vial_in_carousel()
#     rob.close_clamp()
#     rob.open_clamp()
#     rob.move_carousel(32,85)
#     rob.move_electrolyte(n = 12)
#     rob.move_carousel(0, 0)
#     rob.cap_and_return_vial_to_rack(pos)
#     rob.water_sources[i][1] -= 1.2
#     rob.move_electrolyte(n = 4)
# 
#     for _ in range(10):
#         rob.shake(num_shakes=10, slow=True)
#         rob.move_electrolyte(n=1)
# 
#     rob.move_electrolyte(n = 10)
# 
#     draw_test()
#     run_geis("res/10_shakes_10x_slow")     
#     
#     #test 2 10 shakes - length 1 - 10 times - fast
#     draw_viscous()
#     i, pos = rob.next_water_source(1.2)
#     rob.move_vial(rack_disp_official[pos], vial_carousel)
#     rob.uncap_vial_in_carousel()
#     rob.close_clamp()
#     rob.open_clamp()
#     rob.move_carousel(32,85)
#     rob.move_electrolyte(n = 12)
#     rob.move_carousel(0, 0)
#     rob.cap_and_return_vial_to_rack(pos)
#     rob.water_sources[i][1] -= 1.2
#     rob.move_electrolyte(n = 4)
# 
#     for _ in range(10):
#         rob.shake(num_shakes = 200, fast = True)
#         rob.delay(1)
#         rob.move_electrolyte(n=1)
#         rob.delay(1)
# 
#     rob.move_electrolyte(n = 10)
# 
#     draw_test()
#     run_geis("10_shakes_10x_fast")     
# 
#     #test 3
#     draw_viscous()
#     i, pos = rob.next_water_source(1)
#     rob.clean_sensors(pos, n_shakes=50, len_shake=10, fast=True)  
#     rob.water_sources[i][1] -= 1 
#     draw_test()
#     run_geis("res/shake_fast_10x")  
# 
#     #test 4
#     draw_viscous()
#     i, pos = rob.next_water_source(1)
#     rob.clean_sensors(pos, n_shakes=50, len_shake=10, slow=True)
#     rob.water_sources[i][1] -= 1 
#     draw_test()
#     run_geis("res/shake_slow_10x")  
    
    #aug 28 overnight purge tests
    '''#test 1 2x purge
    draw_viscous()

    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2 

    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2 

    draw_test()
    run_geis("res/2x_purge_slow")   

    #test 2 1x purge
    draw_viscous()

    i, pos = rob.next_water_source(4.2)
    rob.purge(pos)
    rob.water_sources[i][1] -= 4.2 

    draw_test()
    run_geis("res/1x_purge_slow")   

    #test 3 shake slow 10forwards 10backwards 10 times
    draw_viscous()
    i, pos = rob.next_water_source(2)
    rob.clean_sensors(pos, n_shakes=10, len_shake=10, slow=True)
    rob.water_sources[i][1] -= 2 
    draw_test()
    run_geis("res/shake_slow_10x")  

    #test 4 shake fast 10forwards 10backwards 50 times 
    draw_viscous()
    i, pos = rob.next_water_source(2)
    rob.clean_sensors(pos, n_shakes=50, len_shake=10, slow=False)
    rob.water_sources[i][1] -= 2 
    draw_test()
    run_geis("res/shake_fast_50x")  

    #test 5 20 slow pumps, shake fast 5F 5B 10 times
    draw_viscous()
    i, pos = rob.next_water_source(2)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 20, purge=True)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 2
    rob.move_electrolyte(n = 20, purge = True)

    i, pos = rob.next_water_source(1)
    rob.clean_sensors(water_location=pos,n_shakes=10, len_shake=5, slow=False)
    rob.water_sources[i][1] -= 1
    draw_test()
    run_geis("res/slow_pump_then_shake_fast_10x")  

    #test 6 20 slow pumps, shake slow 5F 5B 10 times
    draw_viscous()
    i, pos = rob.next_water_source(2)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 20, purge=True)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 2
    rob.move_electrolyte(n = 20, purge = True)

    i, pos = rob.next_water_source(1)
    rob.clean_sensors(water_location=pos,n_shakes=10, len_shake=5, slow=True)
    rob.water_sources[i][1] -= 1

    draw_test()
    run_geis("res/slow_pump_then_shake_slow_10x")  

    #test 7 10 pumps then wait between pumps
    draw_viscous()
    i, pos = rob.next_water_source(1)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n=10, purge=True)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 1

    rob.move_electrolyte(n=5, purge=True)
    for _ in range(20):
        rob.move_electrolyte(n=1, purge=True)
        rob.delay(120)
    draw_test()
    run_geis("res/shake_fast_50x")  

    #test 8 20 pumps extra slow
    draw_viscous()

    i, pos = rob.next_water_source(2)
    rob.move_vial(rack_disp_official[pos], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    for _ in range(20):
        rob.set_pump_speed(0, 5)
        rob.delay(1)
        rob.set_pump_valve(0, int(True))
        rob.delay(1)
        rob.move_pump(0, 0)
        rob.delay(1)
        rob.set_pump_speed(0, 34)
        rob.delay(3)
        rob.set_pump_valve(0, int(False))
        rob.delay(1)
        rob.move_pump(0,2000)
        rob.delay(3)
        rob.delay(150)

    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(pos)
    rob.water_sources[i][1] -= 2

    draw_test()
    run_geis("res/20_pumps_extra_slow")  

    #test 9 slow pumps with hot water at the sensors
    draw_viscous()

    rob.move_vial(heatplate_official[2], vial_carousel)
    rob.uncap_vial_in_carousel()
    rob.close_clamp()
    rob.open_clamp()
    rob.move_carousel(32,85)
    rob.move_electrolyte(n = 20)
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(2, rack = heatplate_official)
    rob.move_electrolyte(20, viscous = True)
    
    draw_test()
    run_geis("res/15 slow pumps hot water")
    
    rob.move_electrolyte(n = 50) # empty out plumbing system
    #aug 27 overnight purge tests
    #test 1 '''
    
    
#     draw_viscous()
# 
#     rob.purge(water[0])
# 
#     draw_test()
#     run_geis("purgetest1")

    #test 2
#     draw_viscous()
# 
#     rob.move_vial(rack_disp_official[water[1]], vial_carousel)
#     rob.uncap_vial_in_carousel()
#     rob.close_clamp()
#     rob.open_clamp()
#     rob.move_carousel(32,85)
#     rob.move_electrolyte(n = 60)
#     rob.move_carousel(0, 0)
#     rob.cap_and_return_vial_to_rack(water[1])
#     rob.move_electrolyte(n = 43)
# 
#     draw_test()
#     run_geis("purgetest2")

    #test 3
#     draw_viscous()
# 
#     rob.clean_sensors(water[2], slow = True)
# 
#     draw_test()
#     run_geis("purgetest3")
# 
#     #test 4
#     draw_viscous()
# 
#     rob.clean_sensors(water[3])
# 
#     draw_test()
#     run_geis("purgetest4")
# 
#     #test 5
#     draw_viscous()
# 
#     rob.move_vial(rack_disp_official[water[4]], vial_carousel)
#     rob.uncap_vial_in_carousel()
#     rob.close_clamp()
#     rob.open_clamp()
#     rob.move_carousel(32,85)
#     rob.move_electrolyte(n = 4, purge = True)
#     rob.move_carousel(0, 0)
#     rob.cap_and_return_vial_to_rack(water[4])
#     rob.delay(300)
#     rob.move_electrolyte(n = 3, purge = True)
#     rob.delay(300)
#     rob.move_electrolyte(n = 5, purge = True)
#     draw_test()
#     run_geis("purgetest5")




