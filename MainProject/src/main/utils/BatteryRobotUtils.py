import sys
sys.path.append('..')

from north import NorthC9
from Locator import *
from .PowderShakerUtils import PowderShaker
from powder_protocols import *
from asp_rack import AspRack
import pandas as pd
import time, math


class BatteryRobot(NorthC9):
    """
    READ DOCS BEFORE USING FUNCTIONS

    child of NorthC9 - inherits North's methods plus methods defined in here
    """
    
    holding_pipette = False
    holding_vial = False
    cap_holder_1_free = True
    cap_holder_2_free = True
    cartridge_on_carousel = None # protocol of powder (not a boolean)
    cartridge_pos= {
         "LiOAc": 1,
         "default": 2,
         "alconox": 3
    }
    pip_id = 0


    def __init__(self, address, network_serial, home=False):
        """
        Startup procedures 
        """
        super().__init__(address, network_serial = network_serial)
        if home:
            self.home_robot() #Robot arm homing
            self.home_carousel() #Robot carousel homing
            self.home_pump(3)  #Pipette pump homing
            self.home_pump(0) #Pump system sensing homing
            self.set_pump_valve(3,0) #Set pump system valve at input position
            

    def map_asp_rack(self, vial_map, vol_map):
        """
        Creates AspRack object as defined in settings folder. See settings/asp_rack.py for details
        """
        self.asp_rack = AspRack(vial_map, vol_map)
        
    def dispense_workflow_auto(self, protocol, n_vials = 1, powder_only = False):
        """
        NOT fully complete yet. It would be better to use dispense_powder_and_scale and dispense_liquid_and_scale
        individually to make solutions for now. 

        populate grid of vials with specific powder AND liquid, one vial by one vial starting from index 0.
        Rack should be filled from right to left
        n_vials is total number of vials to populate, and each column must have 4 vials.
        Each column with vials to populate must have 2 source vials
        
        Function takes in protocol of specific powder to fill vials with. As well as number of vials to fill up
        
        Todo:
        1) figure out way to populate columns of 3,2,1
        2) how to start from specific column
        3) work with multiple powder protocols
        """
        vials_per_col = 4
        self.open_clamp()
        self.open_gripper()
        self.zero_scale()
        
        pow_masses = [10,25,50,100,250] # for full deck, number of elements should equal n_vials/vials_per_col
        liq_volumes = [2, 1, 0.5, 0.25, 0.1, 0.05, 0.025, 0.01] #number of elements should equal n_vials/vials_per_col
        
        data = {
            "Vial_ID": [],
            "time/s":[],
            "PowMass/mg (Intended)":[],
            "PowMass/mg (Real)":[],     
            "LiqVol/ml (Intended)":[],
            "LiqVol/ml (Real)":[]
            }
        
        for dispense_vial_id in range(n_vials):
            data["Vial_ID"].append(dispense_vial_id)
            
            # get vial, place in carousel
            self.move_vial(rack_disp_official[dest_id], vial_carousel)
            self.close_clamp()
            self.close_gripper()
            self.delay(.7)    
            self.uncap()
            self.holding_vial = False
            self.goto_safe(safe_zone)
            self.open_clamp()
            
            start = time.time()
            
            #dispensing powder 
            col = dispense_vial_id // vials_per_col
            mass = pow_masses[col]
            pow_data = self.dispense_powder_and_scale(protocol, dispense_vial_id, mass, False)
            
            data["PowMass/mg (Intended)"].append(pow_data["Intended(mg)"])
            data["PowMass/mg (Real)"].append(pow_data["Real(mg)"])
            
            #dispensing liquid
            vol = liq_volumes[col]
            source_vial_id = 0
            
            if dispense_vial_id % 2 == 0:
                source_vial_id = 0 + column * 2
            else:
                source_vial_id = 1 + column * 2
                
            liq_data = self.dispense_liquid_and_scale(dispense_vial_id, source_vial_id, volume, False)
            data["LiqVol/ml (Intended)"].append(pow_data["Intended(ml)"])
            data["LiqVol/ml (Real)"].append(pow_data["Real(ml)"])
            
            t_taken = time.time() - start
            data["time/s"].append(t_taken)
            
            self.cap_and_return_vial_to_rack(dispense_vial_id)
           
        df = pd.DataFrame(data)
        df.to_csv('res/dispense.csv', index=True, mode='w')


    def dispense_powder_and_scale(self, protocol, dest_id, mass, collect = False, ret = True):
        """
        dispense powder into specified vial (dest_id)
        """
        self.check_remove_pipette()

        if collect:
            self.move_vial(rack_disp_official[dest_id], vial_carousel)
        else:
            self.goto_safe(vial_carousel)
            
        self.uncap_vial_in_carousel()  
        self.move_carousel(68, 77) # carousel moves 68 degrees, 77 mm down
        
        start = time.time()
        p2 = PowderShaker('C', network = self.network)
        dispensed = p2.cl_pow_dispense(robot = self, mg_target = mass, protocol = protocol)
        t_taken = time.time() - start
        
        self.delay(1)
        self.move_carousel(0,0)
        
        #return to rack or not
        if ret:
            self.cap_and_return_vial_to_rack(dest_id)
        else:
            self.close_clamp()
            self.goto_safe(vial_carousel_approach)
            self.cap(torque_thresh = 600)
            self.open_gripper()
            self.open_clamp()
            self.goto_safe(safe_zone)
            
        data = {}
        data["Vial ID"] = dest_id
        #milligrams
        data["Intended"] = mass
        data["Real"] = dispensed
        data["Time Taken(s)"]= t_taken
        return data
    
    def dispense_liquid_vol(self, dest_id, source, target_vol, collect = False, ret = True):
        """
        Dispense {target_vol}ml of liquid into vial with id {dest_id} from vials with id {source_id}.
        Destination vials are from rack_dispense_official while source_vials are from rack_pipette_aspirate
        respectively (see Locators)
        
        Todo:
        1) Keep track of amount of liquid remaining in source vials to determine pipette height when
           drawing liquid 
        """
        self.check_remove_pipette()
        self.goto_safe(rack_asp_official[getattr(self.asp_rack, source)])
        cap_holder_id = self.move_cap_to_holder()
        
        if collect:
            self.move_vial(rack_disp_official[dest_id], vial_carousel)
        else:
            self.goto_safe(vial_carousel)
            
        self.uncap_vial_in_carousel()
        self.get_pipette()
        self.zero_scale()
        
        remaining = target_vol 
        while remaining > 0:
            rack = p_asp_high
            
            if getattr(self.asp_rack, source + "vol") <= 4:
                rack = p_asp_low
            elif getattr(self.asp_rack, source + "vol") <= 6:
                rack = p_asp_mid
            
            self.goto_safe(rack[getattr(self.asp_rack, source)])
            amount = min(remaining, 1)
            self.aspirate_ml(3, amount)
            self.delay(.5)
            self.goto_safe(carousel_dispense)
            self.dispense_ml(3, amount)
            self.delay(.5)
            remaining -= 1
            
            setattr(self.asp_rack,
                    source + "vol",
                    getattr(self.asp_rack, source + "vol") - amount
                    )
        dispensed = self.read_steady_scale()   
        self.goto_safe(safe_zone)
        self.remove_pipette()
        
        if ret:
            self.cap_and_return_vial_to_rack(dest_id)
        else:
            self.close_clamp()
            self.goto_safe(vial_carousel_approach)
            self.cap(torque_thresh = 600)
            self.open_gripper()
            self.open_clamp()
        
        self.move_cap_from_holder(source, cap_holder_id)
        
        data = {}
        data["Vial ID"] = dest_id 
        data["Intended(ml)"]= target_vol
        data["Real(ml)"] = dispensed
        return data
    

    def dispense_liquid_mass(self, dest_id, source, target_mass, density, collect = False, ret = True):
        """
        Dispense liquid based on target mass
        """
        self.check_remove_pipette()
        self.goto_safe(rack_asp_official[getattr(self.asp_rack, source)])
        cap_holder_id = self.move_cap_to_holder()
        
        if collect:
            self.move_vial(rack_disp_official[dest_id], vial_carousel)
        else:
            self.goto_safe(vial_carousel)
            
        self.uncap_vial_in_carousel()
        self.get_pipette()
        self.delay(1)
           
        dispensed = 0 
        while dispensed < target_mass: # repeat until target mass achieved
            rack = p_asp_high
            
            if getattr(self.asp_rack, source + "vol") <= 4:
                rack = p_asp_low
            elif getattr(self.asp_rack, source + "vol") <= 6:
                rack = p_asp_mid
                
            self.zero_scale()
            self.goto_safe(rack[getattr(self.asp_rack, source)])
                  
            amount = min((target_mass - dispensed)/density , 1) #get smaller value between 1, and remaining volume to dispense
            self.aspirate_ml(3, amount)
            self.goto_safe(carousel_dispense)
            self.delay(.5)
            self.dispense_ml(3, amount)
            self.delay(.5)
            dispensed += self.read_steady_scale() #use scale to determine actual mass dispensed
            self.delay(.5)
            setattr(self.asp_rack,
                    source + "vol",
                    getattr(self.asp_rack, source + "vol") - amount
                    )

        self.goto_safe(safe_zone)
        self.remove_pipette()
        
        if ret:
            self.cap_and_return_vial_to_rack(dest_id)
        else:
            self.close_clamp()
            self.goto_safe(vial_carousel_approach)
            self.cap(torque_thresh = 600)
            self.open_gripper()
            self.open_clamp()
        
        self.move_cap_from_holder(source, cap_holder_id)
        
        data = {}
        data["Vial ID"] = dest_id 
        data["Intended(g)"]= target_mass
        data["Real(g)"] = dispensed
        return data
    
    def get_new_cartridge(self, new=None):
        """
        If there is a cartridge on carousel (active cartridge), replace with {new}, where {new} is a protocol for a powder
        E.g. get_new_cartridge(LiOAc) replaces the active cartridge (if present) with the LiOAc cartridge
        If {new} is not specified, robot returns active cartridge to holder without replacing it
        Defined protocols can be found in settings/powder_protocols.py
        """
        #position carousel first
        self.move_carousel(68,77)
        
        if self.cartridge_on_carousel:
            self.goto_safe(active_powder_cartridge)
            self.close_gripper()
            self.delay(1)
            if self.cartridge_pos[self.cartridge_on_carousel.name] == 1:
                self.goto_safe(powder_1)
            elif self.cartridge_pos[self.cartridge_on_carousel.name] == 2:
                self.goto_safe(powder_2)        
            elif self.cartridge_pos[self.cartridge_on_carousel.name] == 3:
                self.goto_safe(powder_3)
            elif self.cartridge_pos[self.cartridge_on_carousel.name] == 4:
                self.goto_safe(powder_4)
                
            self.open_gripper()
            self.cartridge_on_carousel = None
        
        #if user specifies new, place new cartridge on carousel
        if new:
            if self.cartridge_pos[new.name] == 1:
                self.goto_safe(powder_1)
            elif self.cartridge_pos[new.name] == 2:
                self.goto_safe(powder_2)        
            elif self.cartridge_pos[new.name] == 3:
                self.goto_safe(powder_3)
            elif self.cartridge_pos[new.name] == 4:
                self.goto_safe(powder_4)            
            self.close_gripper()
            self.delay(1)
            self.goto_safe(active_powder_cartridge)
            self.open_gripper()
            self.cartridge_on_carousel = new
            
        self.goto_safe(safe_zone)
        self.move_carousel(0,0)
        

    #viscous (29 speed)
    def move_electrolyte(self, draw = True, length = 2000, purge = False, viscous = False, light = False):
        """
        draw = True by default. when draw is true, syringe draws electrolyte from vial
        if draw = False, syringe pushes out electrolyte back into vial (basically moves electrolyte in opposite direction)
        not sure of how many pumps to make yet, so function pumps indefinitely in direction of choosing
        to stop, press ctrl + C

        after testing:
        1) about 8 pumps to draw adequately long column of electrolyte
        2) once drawn, move syringe out of vial, continue pumping air to move electrolyte to electrodes
        3) about 20 pumps to move column of electrolyte to electrodes

        note: position of electrodes was moved, so further testing must be done to determine
        optimum number of pumps for step 3
        
        4 speed settings: purge (to purge plumbing system), viscous, medium, light. Defaults to medium speed.
        Set viscous = True if contents to draw is viscous, and so on for other speeds.
        """
        print("Hit Ctrl+C when you want to stop pumping!")
        v_in = 13 #speed to suck air, default to medium speed
        v_out = 0 # speed to push out air

        if purge:
            v_in, v_out = 5, 5
        elif viscous:
            v_in, v_out = 28, 0
        else: # light
            v_in, v_out = 7, 0
        i = 0
        while True:
            try:
                i += 1
                self.set_pump_speed(0, v_in)
                self.delay(1)
                self.set_pump_valve(0, int(not draw))
                self.delay(1)
                self.move_pump(0,length)
                self.delay(3)
                self.set_pump_speed(0, v_out)
                self.delay(1)
                self.set_pump_valve(0, int(draw))
                self.delay(1)
                self.move_pump(0, 0)
                self.delay(3)
            except KeyboardInterrupt:
                print(i) # print number of pumps
                break

    def move_cap_to_holder(self):
        """
        Helper function to move cap to a free cap holder. Assumes gripper is at target vial's cap's location
        """
        self.close_gripper()
        self.delay(.5)
        self.uncap()
        
        if self.cap_holder_1_free:
            self.goto_safe(cap_holder_1_approach)
            self.cap_holder_1_free = False
            cap_holder_id = 1

        elif self.cap_holder_2_free:
            self.goto_safe(cap_holder_2_approach)
            self.cap_holder_2_free = False
            cap_holder_id = 2

        else:
            raise Exception("Cap holders are taken!")
        
        self.cap(torque_thresh = 600)    
        self.open_gripper()
        
        return cap_holder_id
    
    def move_cap_from_holder(self, source, cap_holder_id):
        """
        Helper function to move cap from holder back to source vial
        """
        if cap_holder_id == 1:
            self.goto_safe(cap_holder_1)
            self.cap_holder_1_free = True
        else:
            self.goto_safe(cap_holder_2)
            self.cap_holder_2_free = True
            
        self.close_gripper()
        self.delay(.5)
        self.uncap()
        self.goto_safe(rack_asp_official_approach[getattr(self.asp_rack, source)])
        self.cap(torque_thresh = 600)
        self.open_gripper()
        self.goto_safe(safe_zone)
        
    def uncap_vial_in_carousel(self):
        """
        Helper to uncap vial in carousel. Assumes gripper is at carousel's vial's cap's location
        """
        self.close_clamp()
        self.delay(.5)
        self.close_gripper()    
        self.uncap()
        self.holding_vial = False
        self.goto_safe(safe_zone)
        self.open_clamp()
    
    def cap_and_return_vial_to_rack(self, dest_id):
        """
        Simple helper function for when procedures in the carousel have been completed.
        This function caps the vial, and returns it to its original position.
        Takes in the vial's position on the dispense section of the main rack and returns it there 
        """
        #cap and return to rack
        self.close_clamp()
        self.goto_safe(vial_carousel_approach)
        self.cap(torque_thresh = 600)
        self.holding_vial = True
        self.open_clamp()                
        self.goto_safe(rack_disp_official[dest_id])
        self.open_gripper()
        self.holding_vial = False
        self.move_z(400)
                             
    def calc_liquid_mol(self, mol, gram, molmass):
        """
        Calculates how much liquid to dispense to get a certain Molarity
        """

        liquidAmount = gram/(molmass*mol)
        return(liquidAmount)
        
    def move_vial(self, src_loc, dest_loc):
        """
        Move vial between two different locations
        """
        self.goto_safe(src_loc)
        self.close_gripper()
        self.delay(0.7)
        self.goto_safe(dest_loc)
        self.open_gripper()
            
    def get_pipette(self):
        """
        gets new pipette at specified position {pip_index} from pipette rack. Will throw an error if robot
        is holding a vial.
        Pipette rack is indexed as follows:
          47 ...... 8 5 2
          46 ...... 7 4 1
          45 ...... 6 3 0
        By default, robot takes pipette from index 0 (bottom right corner as shown above)
        """
        # Checks if robot is currently holding a vial 
        if self.holding_vial:
            raise Exception("Holding vial! Unsafe to perform pipette operations")
        
        pipette_order = [i for i in range(2, 48, 3)] \
            + [i for i in range(1, 48, 3)] \
            + [i for i in range(0, 48, 3)]
        
        print(f"getting pipette at index {self.pip_id}")
        self.goto_safe(pipette_grid[pipette_order[self.pip_id]])
        self.increment_pip_id()
        self.move_z(400) # lift up before moving to safe spot
        self.goto_safe(safe_zone) # go to safe zone
        self.holding_pipette = True


    def check_remove_pipette(self):
        """
        If robot is holding pipette, remove it
        """
        if self.holding_pipette:
            print("Rob is holding pipette! Removing pipette...")
            self.remove_pipette()      


    def remove_pipette(self):
        """
        Simple function that removes pipette
        """
        self.goto_safe(p_remover_capture_approach)
        self.goto(p_remover_capture)
        self.move_z(400)
        self.holding_pipette = False
        self.goto_safe(safe_zone) # go to safe zone
        

    def increment_pip_id(self):
        """
        Increment to get next pipette. Return to first index after 48th pipette
        """
        self.pip_id += 1
        if self.pip_id >= 48:
            self.pip_id = 0
    

    def stir_vial(self, speed):
        """
        Activate magnetic stirrer for heat plate
        """
        t8 = BatteryRobot('B', network=self.network)
        self.spin_axis(6, speed)

    