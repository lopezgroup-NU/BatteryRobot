from north import NorthC9
from Locator import *
from PowderShakerUtils import PowderShaker
from powder_protocols import *
import pandas as pd
import time



#child of NorthC9 - has all of North's methods plus methods defined in here
class BatteryRobot(NorthC9):
    holding_pipette = False
    holding_vial = False
#     t8 = BatteryRobot('B', network=self.network)
#     p2 = BatteryRobot('C', network=self.network)

#     def __init__(self):        
#         self.home_robot() #Robot arm homing
#         self.home_carousel() #Robot carousel homing
#         self.home_pump(3)  #Pipette pump homing
#         self.home_pump(0) #Pump system sensing homing
#         self.set_pump_valve(3,0) #Set pump system valve at input position
#         t8 = NorthC9("B", network=c9.network)
#         for temp_channel in range(8):
#             t8.disable_channel(temp_channel) #Clears the temp Sensor
    def dispense_powder_and_scale(self): 
        dispense_vials = 1
        masses = [250, 100, 50, 25, 10] #mg
        
        p2 = PowderShaker('C', network = self.network)
        self.check_remove_pipette
        with open("dispensescale_powder_results.txt", "w") as f:
            f.write("Results of dispensing and scaling powder: \n")
            
            for dispense_vial_id in range(dispense_vials):
                column = dispense_vial_id // 4
                mass = masses[column]
                
                self.open_clamp()
                self.open_gripper()
                self.zero_scale()
                
                self.get_vial_from_rack(dispense_vial_id, rack_dispense_official)
                self.goto_safe(vial_carousel)
                self.close_clamp()
                self.delay(.7)
                
                self.uncap()
                self.goto_safe(safe_zone)
                
                self.move_carousel(68, 77) # carousel moves 68 degrees, 75 mm down
                p2.cl_pow_dispense(mg_target = mass, protocol = LiOAc)
                
#                 self.move_carousel(0,0)
#                 
#                 self.goto_safe(carousel_cap_approach)
#                 self.cap()
#                 self.open_gripper()
#                 self.open_clamp()
#                 self.goto_safe(safe_zone)
# 
#                 self.delay(.5)
#                 reading = str(self.read_steady_scale())
#                 f.write(f"Intended: {mass}ml Real: {reading}g Vial: {dispense_vial_id}\n")
                
    def dispense_liquid_and_scale(self):
        pip_id = 0
        column = 0 #per value of volume wanted
        dispense_vials = 32
        aspirate_vial_id = 0
        volumes = [2, 1, 0.5, 0.25, 0.1, 0.05, 0.025, 0.01]  
        
        self.check_remove_pipette()
        
        with open("dispensescale_results.txt", "w") as f:
            f.write("Results of dispensing and scaling: \n")
            
            for dispense_vial_id in range(dispense_vials):
                
                column = dispense_vial_id // 4
                volume = volumes[column]
                
                if dispense_vial_id % 2 == 0:
                    aspirate_vial_id = 0 + column * 2
                else:
                    aspirate_vial_id = 1 + column * 2
                
                self.open_clamp()
                self.open_gripper()
                
                self.zero_scale()
                self.get_vial_from_rack(dispense_vial_id, rack_dispense_official)
                self.goto_safe(vial_carousel)
                self.close_clamp()
                self.delay(.7)
                self.uncap()
                self.get_pipette(pip_id)
                self.goto_safe(rack_pipette_aspirate[aspirate_vial_id])
                if volume == 2:
                    self.aspirate_ml(3,volume-1)
                    self.delay(.5)
                    self.goto_safe(carousel_dispense)
                    self.dispense_ml(3,volume-1)
                    self.delay(.5)
                    self.goto_safe(rack_pipette_aspirate[aspirate_vial_id])
                    self.aspirate_ml(3,volume-1)
                    self.delay(.5)
                    self.goto_safe(carousel_dispense)
                    self.dispense_ml(3,volume-1)
                    self.delay(.5)
                else:
                    self.aspirate_ml(3,volume)
                    self.delay(.5)
                    self.goto_safe(carousel_dispense)
                    self.dispense_ml(3,volume)
                    self.delay(.5)
                self.remove_pipette()
                self.goto_safe(carousel_cap_approach)
                self.cap()
                self.open_gripper()
                self.open_clamp()
                self.delay(.5)
                reading = str(self.read_steady_scale())
                self.delay(.5)
                f.write(f"Intended: {volume}ml Real: {reading}g Vial: {dispense_vial_id}\n")
                self.close_gripper()
                self.goto_safe(rack_dispense_official[dispense_vial_id])
                self.open_gripper()
                pip_id += 1
                      
            f.close()
        
    def dispense_liquid_and_scale2(self):
        pip_id = 0
        column = 0 #per value of volume wanted
        dispense_vials = 32
        aspirate_vial_id = 0
        volumes = [2, 1, 0.5, 0.25, 0.1, 0.05, 0.025, 0.01]  
        
        self.check_remove_pipette()
        
        with open("dispensescale2_results.txt", "w") as f:
            f.write("Results of dispensing and scaling: \n")
            
            for dispense_vial_id in range(dispense_vials):
                
                column = dispense_vial_id // 4
                volume = volumes[column]
                
                if dispense_vial_id % 2 == 0:
                    aspirate_vial_id = 0 + column * 2
                else:
                    aspirate_vial_id = 1 + column * 2
                
                self.open_clamp()
                self.open_gripper()
                self.get_vial_from_rack(dispense_vial_id, rack_dispense_official)
                self.goto_safe(vial_carousel)
                self.close_clamp()
                self.delay(.7)
                self.uncap()
                self.open_clamp()
                self.get_pipette(pip_id)
                self.goto_safe(rack_pipette_aspirate[aspirate_vial_id])
                self.delay(1)
                if volume == 2:
                    self.aspirate_ml(3,volume-1)
                    self.delay(.5)
                    self.goto_safe(carousel_dispense)
                    self.delay(1)
                    self.zero_scale()
                    self.delay(1)
                    self.dispense_ml(3,volume-1)
                    self.delay(.5)
                    self.goto_safe(rack_pipette_aspirate[aspirate_vial_id])
                    self.aspirate_ml(3,volume-1)
                    self.delay(.5)
                    self.goto_safe(carousel_dispense)
                    self.dispense_ml(3,volume-1)
                    self.delay(.5)
                else:
                    self.aspirate_ml(3,volume)
                    self.delay(.5)
                    self.goto_safe(carousel_dispense)
                    self.delay(1)
                    self.zero_scale()
                    self.delay(1)
                    self.dispense_ml(3,volume)
                    self.delay(.5)
                reading = str(self.read_steady_scale())
                self.delay(.5)
                f.write(f"Intended: {volume}ml Real: {reading}g Change in Vial: {dispense_vial_id}\n")
                self.remove_pipette()
                self.close_clamp()
                self.goto_safe(carousel_cap_approach)
                self.cap()
                self.open_gripper()
                self.open_clamp()
                self.delay(.5)
                self.close_gripper()
                self.goto_safe(rack_dispense_official[dispense_vial_id])
                self.open_gripper()
                pip_id += 1
                      
            f.close()
                        
    def get_vial_from_rack(self, vial_id, rack_type): #rack_official or rack_dispense_official
        self.check_remove_pipette()
        print(f"getting vial at index {vial_id}")
        self.open_gripper()
        self.goto_safe(rack_type[vial_id])
        self.close_gripper()
        time.sleep(0.5)
        self.move_z(400)
        self.holding_vial = True
    
    def check_remove_pipette(self):
        if self.holding_pipette:
            print("Rob is holding pipette! Removing pipette...")
            self.remove_pipette()      

    def remove_pipette(self):
        self.goto_safe(p_remover_capture_approach)
        self.goto(p_remover_capture)
        self.move_z(400)
        self.holding_pipette = False
        
    def get_pipette(self, pip_index=0):
    
        pipette_order = [i for i in range(2, 48, 3)] \
            + [i for i in range(1, 48, 3)] \
            + [i for i in range(0, 48, 3)]
        
        print(f"getting pipette at index {pip_index}")
        self.goto_safe(pipette_grid[pipette_order[pip_index]])
        self.move_z(400) # must lift up before moving to safe spot
        self.move_xyz(100,40,300) # safe spot
        self.holding_pipette = True

        
        

        

        
        
        
        
