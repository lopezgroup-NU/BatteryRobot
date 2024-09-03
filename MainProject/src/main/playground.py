from utils import BatteryRobot,PowderShaker,T8
from Locator import *
from settings import powder_protocols, AspRack
from utils.PStat.geis import *
import time
import toolkitpy as tkp
from temper_windows import TemperWindows

rob = BatteryRobot('A', network_serial='AU06EZ1P', home = True)
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
def draw_test():
    rob.move_vial(rack_disp_official[test_sol], vial_carousel)
    rob.uncap_vial_in_carousel()  
    rob.draw_to_sensor()
    rob.move_carousel(0, 0)
    rob.cap_and_return_vial_to_rack(test_sol)
rob.map_water_source(csv_path = "settings/water_sources.csv")
test_sol = 0
viscous = 1

def test_purge_protocols():
    '''
    kinds of cleaning

        1. Slow Purge full system single direction
        2. Fast Purge full vial single direction
        3. Shake Purge 12 pumps slow both directions
        4. 
        5. Soak Purge 4 pumps leave at sensor for 5min
    '''
    rob.map_water_source(csv_path = "settings/water_sources.csv")
    test_sol = 0
    viscous = 1

    def draw_viscous():
        rob.move_vial(rack_disp_official[viscous], vial_carousel)
        rob.uncap_vial_in_carousel()  
        rob.draw_to_sensor(viscous=True)
        rob.move_carousel(0, 0)
        rob.cap_and_return_vial_to_rack(viscous)
        rob.delay(60)
        rob.move_electrolyte(n = 3, viscous = True)
        rob.delay(60)
        rob.move_electrolyte(n = 5, viscous = True)


    def draw_test():
        rob.move_vial(rack_disp_official[test_sol], vial_carousel)
        rob.uncap_vial_in_carousel()  
        rob.draw_to_sensor()
        rob.move_carousel(0, 0)
        rob.cap_and_return_vial_to_rack(test_sol)
        
        
    #sept 3 purge tests
        
    #test 1 10 shakes - length 1 - 10 times - slow
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
    rob.water_sources[i][1] -= 1
    rob.move_electrolyte(n = 5)

    for _ in range(10):
        for _ in range(10):
                rob.move_electrolyte(n = 1, purge = True)
                rob.move_electrolyte(n = 1, draw = False, purge = True)
        
        rob.move_electrolyte(n=1)

    rob.move_electrolyte(n = 20)

    draw_test()
    run_geis("res/10_shakes_10x_slow")     
    
    #test 2 10 shakes - length 1 - 10 times - slow
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
    rob.water_sources[i][1] -= 1
    rob.move_electrolyte(n = 5)

    for _ in range(10):
        for _ in range(50):
                rob.move_electrolyte(n = 1)
                rob.move_electrolyte(n = 1, draw = False)
        
        rob.move_electrolyte(n=1)

    rob.move_electrolyte(n = 20)

    draw_test()
    run_geis("10_shakes_10x_fast")     

    #test 3
    draw_viscous()
    i, pos = rob.next_water_source(1)
    rob.clean_sensors(pos, n_shakes=50, len_shake=10, slow=False)
    rob.water_sources[i][1] -= 1 
    draw_test()
    run_geis("res/shake_fast_10x")  

    #test 4
    draw_viscous()
    i, pos = rob.next_water_source(1)
    rob.clean_sensors(pos, n_shakes=50, len_shake=10, slow=True)
    rob.water_sources[i][1] -= 1 
    draw_test()
    run_geis("res/shake_slow_10x")  

    #test 5
    draw_viscous()

    rob.move_vial(heatplate_official[2], rack_disp_official[17])
    rob.clean_sensors(17, n_shakes=50, len_shake=10, slow=False)
    rob.move_vial(rack_disp_official[17], heatplate_official[2])
    draw_test()
    run_geis("res/shake_fast_10x_hot")

    #test 6
    draw_viscous()

    rob.move_vial(heatplate_official[2], rack_disp_official[17])
    rob.purge(17)
    rob.move_vial(rack_disp_official[17], heatplate_official[2])
    draw_test()
    run_geis("res/purge_hot")
    
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




