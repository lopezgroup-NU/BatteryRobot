import sys
sys.path.append('C:\\Users\\llf1362\\Desktop\\BatteryRobot\\MainProject\\src\\main\\settings')
#add setings folder to path ( otherwise python can't import protocols and settings)

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

#     def __init__(self):        
#         self.home_robot() #Robot arm homing
#         self.home_carousel() #Robot carousel homing
#         self.home_pump(3)  #Pipette pump homing
#         self.home_pump(0) #Pump system sensing homing
#         self.set_pump_valve(3,0) #Set pump system valve at input position
#         t8 = NorthC9("B", network=c9.network)
#         for temp_channel in range(8):
#             t8.disable_channel(temp_channel) #Clears the temp Sensor

    def dispense_workflow(self):
        pass
    
    def dispense_powder_and_scale(self, protocol, n_vials = 20, vials_per_col = 4): 
        masses = [10,25,50,100,250] #number of different masses should equal n_vials/vials_per_col
        
        p2 = PowderShaker('C', network = self.network)
        self.check_remove_pipette()
        
        data = {
            "Intended(mg)": [],
            "Real(mg)": [],
            "Time Taken(s)": []
            }
            
        for dispense_vial_id in range(n_vials):
            column = dispense_vial_id // vials_per_col
            mass = masses[column]
            
            self.open_clamp()
            self.open_gripper()
            self.zero_scale()
            
            self.get_vial_from_rack(dispense_vial_id, rack_dispense_official)
            self.goto_safe(vial_carousel)
            self.close_clamp()
            self.delay(.7)
            
            self.uncap()
            self.holding_vial = False
            self.goto_safe(safe_zone)
            self.open_clamp()
            
            self.move_carousel(68, 77) # carousel moves 68 degrees, 75 mm down
            start = time.time()
            dispensed = p2.cl_pow_dispense(robot = self, mg_target = mass, protocol = protocol)
            t_taken = time.time() - start
            self.delay(1)
            self.move_carousel(0,0)
            
            self.delay(.5)

            data["Intended(mg)"].append(mass)
            data["Real(mg)"].append(dispensed)
            data["Time Taken(s)"].append(t_taken)
            self.close_clamp()
            self.goto_safe(carousel_cap_approach)
            self.cap()
            self.holding_vial = True
            self.open_clamp()                
            self.goto_safe(rack_dispense_official[dispense_vial_id])
            self.open_gripper()
        
        self.goto_safe(safe_zone)
#         df = pd.DataFrame(data)
#         df.to_csv('res/powder_dispense.csv', index=True, mode='w')
        
    def dispense_liquid_and_scale(self, n_vials = 32, vials_per_col = 4):
        pip_id = 0
        column = 0 #per value of volume wanted
        aspirate_vial_id = 0
        volumes = [2, 1, 0.5, 0.25, 0.1, 0.05, 0.025, 0.01]  
        
        self.check_remove_pipette()
        
        data = {
            "Intended(ml)": [],
            "Real(ml)": [],
            }        
        
        for dispense_vial_id in range(n_vials):
                
            column = dispense_vial_id // vials_per_col
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
            self.holding_vial = False
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

            data["Intended(ml)"].append(volume)
            data["Real(ml)"].append(reading)
            self.remove_pipette()
            self.close_clamp()
            self.goto_safe(carousel_cap_approach)
            self.cap()
            self.holding_vial = True
            self.open_clamp()
            self.delay(.5)
            self.goto_safe(rack_dispense_official[dispense_vial_id])
            self.open_gripper()
            self.holding_vial = False
            pip_id += 1
        self.goto_safe(safe_zone)
#         df = pd.DataFrame(data)
#         df.to_csv("res/liquid_dispense.csv", index=True, mode = 'w')
                        
    def get_vial_from_rack(self, vial_id, rack_type): #racks/heatplate 
        print(f"getting vial at index {vial_id}")
        self.open_gripper()
        self.goto_safe(rack_type[vial_id])
        self.close_gripper()
        time.sleep(0.5)
        self.move_z(400)
#         self.holding_vial = True
        
    
    def check_remove_pipette(self):
        if self.holding_pipette:
            print("Rob is holding pipette! Removing pipette...")
            self.remove_pipette()      

    def remove_pipette(self):
        self.goto_safe(p_remover_capture_approach)
        self.goto(p_remover_capture)
        self.move_z(400)
        self.holding_pipette = False
    
    """
     
    """
    def get_pipette(self, pip_index=0):
        # Checks if robot is currently holding a vial, will throw an error if True.
        
        if self.holding_vial:
            raise Exception("Holding vial! Unsafe to perform pipette operations")
        
        pipette_order = [i for i in range(2, 48, 3)] \
            + [i for i in range(1, 48, 3)] \
            + [i for i in range(0, 48, 3)]
        
        print(f"getting pipette at index {pip_index}")
        self.goto_safe(pipette_grid[pipette_order[pip_index]])
        self.move_z(400) # must lift up before moving to safe spot
        self.move_xyz(100,40,300) # safe spot
        self.holding_pipette = True

        
        

        

        
        
        
        
