from north import NorthC9
from Locator import *

class BatteryRobot(NorthC9):
    
    def home(self):
        self.home_robot()
        
    def start_robot(self):        
        self.home_robot() #Robot arm homing
        self.home_carousel() #Robot carousel homing
        self.home_pump(3)  #Pipette pump homing
        self.home_pump(0) #Pump system sensing homing
        self.set_pump_valve(3,0) #Set pump system valve at input position
        for temp_channel in range(8):
            t8.disable_channel(temp_channel) #Clears the temp Sensor
            
    def get_pipette(self, pip_index=0):
        print(f"getting pipette at index {pip_index}")
        self.goto_safe(pipette_grid[pip_index])
        self.move_z(400)
        self.holding_pipette = True
        
    def move_pipette(self): #avoid collision after picking up new pipette
        self.move_xyz(100,40,300)

    def remove_pipette(self):
        self.goto_safe(p_remover_capture_approach)
        self.goto(p_remover_capture)
        self.move_z(400)
        self.holding_pipette = False
        
    def get_vial_from_rack(self, vial_index=0):
        print(f"getting vial at index {vial_index}")
        self.open_gripper()
        self.goto_safe(rackOfficial[0])
        self.close_gripper()
        self.move_z(400)

        

        
        
        
        
