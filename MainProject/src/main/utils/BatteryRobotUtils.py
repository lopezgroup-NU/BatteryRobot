import sys
sys.path.append('..')
sys.path.append(r'C:\Users\llf1362\Documents\NorthIDE\Lib\site-packages')

from north import NorthC9
from Locator import *
from .PowderShakerUtils import PowderShaker
from config import powder_protocols, SourceRack, PowderProtocol
import pandas as pd
import time, pathlib

class BatteryRobot(NorthC9):
    """
    READ DOCS BEFORE USING FUNCTIONS

    child of NorthC9 - inherits North's methods plus methods defined in here
    """
    
    holding_pipette = False # is arm holding pipette
    holding_vial = False # is arm holding cap
    cap_holder_1_free = True 
    cap_holder_2_free = True
    cartridge_on_carousel: PowderProtocol = None
    cartridge_pos= {
         "LiOAc": 1,
         "default": 2,
         "alconox": 3
    }
    pip_id = 0
    #maps rack_disp_official indexes to their vial's volume(ml)
    solution_vols = {
        0: 6,
        1: 8,
        2: 8,
        3: 8,
        4: 8,
        5: 8,
        7: 8,
        8: 8,
        9: 8,
    } 
    saturations = {}

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

    def run(filepath):
        """
        Takes input file path containing test details. Synthesizes and tests each specified formulation.
        Assume input file contains n tests. Each test is 3 lines - combination, test name, test conditions.
        Each test i (0 <= i <= n-1) begins at line 3i.
        """
        f = open(filepath) 
        processed = 0

        while True:
            # first line of test - combination 
            # synthesis step
            line = f.readline()
            if not line: #if empty, means EOF(end of file)
                break
            combination = line.split()
            

            # second line of test - name
            line = f.readline()
            if not line: #if empty, means EOF(end of file)
                break
            test_name = line

            # third line of test - conditions 
            # test step
            line = f.readline()
            if not line: #if empty, means EOF(end of file)
                break
            test_conditions = line.split(",")

            test_types, test_params = test_conditions[0], test_conditions[1]

            if "geis" in test_types or "GEIS" in test_types:
                geis = True
                geis_params = test_params[0]

                if "cv" in test_types or "CV" in test_types:
                    cv = True
                    cv_params = test_params[1]
                else:
                    cv = False
            else:
                geis = False
                cv = True
                cv_params = test_params[0]
                
            params = {}

            if geis:
                params["InitFreq"] = geis_params[0]
                params["FinalFreq"] = geis_params[1]
                params["Amplitude"] = geis_params[2]
            if cv:
                params["Point1"] = cv_params[0]
                params["Point2"] = cv_params[1]
                params["Rate"] = cv_params[2]

            prompt = input("Rack limit reached. Enter anything to continue, else enter N")
            if prompt.upper() == "N":
                break
            
            processed += 1
            #loop again, do next test
        
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
            self.move_vial(rack_disp_official[dispense_vial_id], vial_carousel)
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
                source_vial_id = 0 + col * 2
            else:
                source_vial_id = 1 + col * 2
                
            liq_data = self.dispense_liquid_vol(dispense_vial_id, source_vial_id, vol, False)
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
        self.goto_safe(rack_source_official[getattr(self.source_rack, source)])
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
            
            if getattr(self.source_rack, source + "vol") <= 4:
                rack = p_asp_low
            elif getattr(self.source_rack, source + "vol") <= 6:
                rack = p_asp_mid
            
            self.goto_safe(rack[getattr(self.source_rack, source)])
            amount = min(remaining, 1)
            self.aspirate_ml(3, amount)
            if amount < 1:
                self.move_z(200)
                self.aspirate_ml(3, 1 - amount)
            self.delay(.5)
            self.goto_safe(carousel_dispense)
            self.dispense_ml(3, 1)
            self.delay(.5)
            remaining -= 1
            
            setattr(self.source_rack,
                    source + "vol",
                    getattr(self.source_rack, source + "vol") - amount
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
        self.goto_safe(rack_source_official[getattr(self.source_rack, source)])
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
            
            if getattr(self.source_rack, source + "vol") <= 4:
                rack = p_asp_low
            elif getattr(self.source_rack, source + "vol") <= 6:
                rack = p_asp_mid
                
            self.zero_scale()
            self.goto_safe(rack[getattr(self.source_rack, source)])
                  
            amount = min((target_mass - dispensed)/density , 1) #get smaller value between 1, and remaining volume to dispense
            self.aspirate_ml(3, amount)
            if amount < 1:
                self.move_z(200)
                self.aspirate_ml(3, 1 - amount)
            self.delay(.5)
            self.goto_safe(carousel_dispense)
            self.dispense_ml(3, 1)
            self.delay(.5)
            dispensed += self.read_steady_scale() #use scale to determine actual mass dispensed
            self.delay(.5)
            setattr(self.source_rack,
                    source + "vol",
                    getattr(self.source_rack, source + "vol") - amount
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
    
    def reset_pump(self):
        self.set_pump_speed(0, 15)        
        self.set_pump_valve(0, 0)
        self.move_pump(0, 0)
    
    def pump_helper(self, length = 1300, v_in = 13, v_out= 0, draw=True):
        """
        Helper function to be used when pumping liquids from carousel.
        
        """
        self.set_pump_speed(0, v_out)
        self.set_pump_valve(0, int(not draw))
        self.move_pump(0, 0)
        self.set_pump_speed(0, v_in)
        self.set_pump_valve(0, int(draw))
        self.move_pump(0,length)
        print("pumped")
    
    #viscous (29 speed)
    def move_electrolyte(self, n = None, draw = True, length = 2000, extra_slow = False, purge = False, viscous = False, light = False):
        """
        if n is specified, pump will pump n times. Else runs indefinitely.
        
        draw = True by default. when draw is true, syringe draws electrolyte from vial
        if draw = False, syringe pushes out electrolyte back into vial (basically moves electrolyte in opposite direction)
        not sure of how many pumps to make yet, so function pumps indefinitely in direction of choosing (unless n is specified)
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
        v_in = 13 #speed to suck air, default to medium speed
        v_out = 0 # speed to push out air

        if purge:
            v_in, v_out = 30, 5
        elif extra_slow:
            v_in, v_out = 40, 5
        elif viscous: # 60 seconds per pump
            v_in, v_out = 35, 0
        elif light:
            v_in, v_out = 1, 0

        self.reset_pump()
        
#         self.move_carousel(33,80) #70 for mid
        if n:
            for i in range(n):
                self.pump_helper(length = length, v_in = v_in, v_out = v_out, draw = draw)

        else:
            i = 0
            print("Hit Ctrl+C when you want to stop pumping!")
            while True:
                try:
                    i += 1
                    self.pump_helper(length = length, v_in = v_in, v_out = v_out, draw = draw)
                except KeyboardInterrupt:
                    print(i) # print number of pumps
                    break

        self.reset_pump()

    def draw_to_sensor(self, id, length = 1300, purge = False, viscous = False, light = False, special = False):
        """
        Assume open vial placed between clamps. Draws 5 pumps of electrolyte, and moves it to the first sensor
        """
        v_in = 20 #speed to draw, default to medium speed
        v_out = 0 # speed to push out air

        if purge:
            v_in, v_out = 35, 5
        elif viscous: # 60 seconds per pump
            v_in, v_out = 35, 0
        elif light:
            v_in, v_out = 1, 0        

        self.close_clamp()
        self.delay(.5)
        self.reset_pump()
        current_height = self.get_needle_height(id)
        self.move_carousel(33, current_height)
        
        self.pump_helper(length = length, v_in = v_in, v_out = v_out)
        self.solution_vols[id] -= 0.4 * length/1250 #  length 1250 roughly equal to 0.4ml
        
        self.move_carousel(0,0)
        if special:
            self.open_clamp()
            self.move_vial(vial_carousel, rack_disp_official[id])
        else:
            self.cap_and_return_vial_to_rack(id)
                
        for _ in range(2):
            self.pump_helper(length = length, v_in = v_in, v_out = v_out)
        
        self.pump_helper(length = 200, v_in = v_in, v_out = v_out)
        self.reset_pump()

    def purge(self, water_location, speed=30, rack = rack_disp_new, n_pumps = 6, length = 3000):
        """
        Purge plumbing system
        Full vial needs total length 18000
        If all the way to brim, length 20000
        """
        self.move_carousel(0, 0)
        self.move_vial(rack[water_location], vial_carousel)

        self.uncap_vial_in_carousel()  
        self.move_carousel(33, 85) # carousel moves 33 degrees, 85 mm down
        
        for _ in range(n_pumps):
            self.pump_helper(length = length, v_in = speed, v_out = 5)

        self.move_carousel(0, 0)
        self.cap_and_return_vial_to_rack(water_location, rack)
        
        for _ in range(n_pumps):
            self.pump_helper(length = length, v_in = 15, v_out = 5)

    def old_school_purge(self, water_location, speed=30, rack = rack_disp_official, n_pumps = 6, length = 3000):
            """
            Purge plumbing system
            """
            self.move_carousel(0, 0)
            self.move_vial(rack[water_location], vial_carousel)
            self.close_clamp()
            self.goto_safe(safe_zone)
            self.move_carousel(33, 85) # carousel moves 33 degrees, 85 mm down
            for _ in range(n_pumps):
                self.pump_helper(length = length, v_in = speed, v_out = 5)

            self.move_carousel(0, 0)
            self.open_clamp()
            self.move_vial(vial_carousel, rack[water_location])

            for _ in range(n_pumps):
                self.pump_helper(length = length, v_in = speed, v_out = 5)

            self.reset_pump()

    def purge_hot(self, water_location, speed = 30, n_pumps = 6):
        """
        Purge plumbing system with hot water
        """
        self.move_carousel(0, 0)
        self.move_vial(heatplate_official[water_location], vial_carousel)
        
        self.uncap_vial_in_carousel()  
        self.move_carousel(33, 85) # carousel moves 33 degrees, 85 mm down
        
        for _ in range(2):
            self.pump_helper(length = 2000, v_in = 15, v_out = 5)
        
        for _ in range(n_pumps - 2):
            self.pump_helper(length = 2000, v_in = speed, v_out = 5)
            
        self.move_carousel(0, 0)
        self.cap_and_return_vial_to_rack(water_location, heatplate_official)
        
        for _ in range(n_pumps):
            self.pump_helper(length = 2000, v_in = 15, v_out = 5)
        

    def get_needle_height(self, id):
        if self.solution_vols[id] <= 5:
            return 85
        elif self.solution_vols[id] <= 6:
            return 75
        elif self.solution_vols[id] <= 7:
            return 70
        else:
            return 65

    def get_new_cartridge(self, new):
        """
        Replace cartridge on carousel (active cartridge) with {new}, where {new} is a protocol for a powder
        E.g. get_new_cartridge(LiOAc) replaces the active cartridge (if present) with the LiOAc cartridge
        Defined protocols can be found in settings/powder_protocols.py
        """
        #position carousel first
        self.move_carousel(68,77)
        self.goto_safe(active_cartridge)
        self.close_gripper()
        self.delay(1)
        self.goto_safe(cartridge_holder)  
        self.open_gripper()

        if new.name not in self.cartridge_pos:
            raise Exception("No such powder")
        
        new_pos = self.cartridge_pos[new.name]
        if new_pos == 1:
            self.goto_safe(powder_1)
        elif new_pos == 2:
            self.goto_safe(powder_2)        
        elif new_pos == 3:
            self.goto_safe(powder_3)
        self.cartridge_pos.pop(new.name)

        self.close_gripper()
        self.delay(1)
        self.goto_safe(active_cartridge)
        self.open_gripper()
        self.cartridge_pos[self.cartridge_on_carousel.name] = new_pos
        self.cartridge_on_carousel = new

        self.goto_safe(cartridge_holder)  
        self.close_gripper()
        self.delay(1)
        if new_pos == 1:
            self.goto_safe(powder_1)
        elif new_pos == 2:
            self.goto_safe(powder_2)        
        elif new_pos == 3:
            self.goto_safe(powder_3)
        self.open_gripper()
        self.goto_safe(safe_zone)
        self.move_carousel(0,0)

    def get_pip_height(self, vial):
        """
        Return appropriate pipette height given target solution to draw from. Make sure solution name is identical
        to one in source_rack.csv
        """
        try:
            vol = getattr(self.source_rack, vial + "_vol")
            if vol <= 2:
                return "Unreachable volume"
            elif vol <= 4:
                return p_asp_low
            elif vol <= 6:
                return p_asp_mid
            else:
                return p_asp_high

        except:
            print("No vial with this name!")

    def make_mixture(self, dest, args):
        """
        Takes arbitrary number of params depending on which components form the mixture
        Assume args is list of 2-tuples e.g. [(name1, conc1, sat1),(name2, conc2, sat2)] 
        """
        self.move_vial(rack_disp_official[dest], vial_carousel)
        self.move_cap_to_holder()

        first_component = args[0]
        second_component = args[1]

        vols = self.calc_vol(args)

        
        for chemical, conc in args:
            self.goto_safe(rack_source_official[self.source_rack[chemical]])
    
    def calc_vol(self, s1, s2, s1_conc, s2_conc, target1, target2, target_vol = 8):
        """
        Uses small volume to find density of each input. 
        Find volumes to reach 1g of solution using ratios from calc_liquid_molal. Scale as needed.  
        """

        s1_prop, s2_prop, water_prop = self.calc_liquid_molal(s1_conc, s2_conc, target1, target2)

        water_v = water_prop/0.9998 

        rack = self.get_pip_height(s1)
        self.zero_scale()
        self.goto_safe(rack[self.source_rack[s1]])
        self.delay(0.5)
        self.aspirate_ml(3, 0.1)
        self.delay(0.5)
        self.move_z(200)
        self.aspirate_ml(3, 0.9)
        self.delay(0.5)
        self.goto_safe(carousel_dispense)
        self.dispense_ml(3, 1)
        s1_mass = self.read_steady_scale()
        s1_p = s1_mass/0.1 #should we use a test vial? or use the same vial that we ran the density tests in later
        s1_v = s1_prop/s1_p

        rack = self.get_pip_height(s2)
        self.zero_scale()
        self.goto_safe(rack[self.source_rack[s2]])
        self.delay(0.5)
        self.aspirate_ml(3, 0.1)
        self.delay(0.5)
        self.move_z(200)
        self.aspirate_ml(3, 0.9)
        self.delay(0.5)
        self.goto_safe(carousel_dispense)
        self.dispense_ml(3, 1)
        s2_mass = self.read_steady_scale()
        s2_p = s2_mass/0.1 #should we use a test vial? or use the same vial that we ran the density tests in later
        s2_v = s2_prop/s2_p

        return s1_v, s2_v, water_v

    def calc_liquid_mol(self, mol, gram, molmass):
        """
        Calculates how much liquid to dispense to get a certain Molarity
        """
        liquidAmount = gram/(molmass*mol)
        return(liquidAmount)
    
    def calc_liquid_molal(first, second, target1, target2):
        """
        Takes in the molals of two solutions. Returns amount of each to reach target ratio (target1:target2) of final solution.
        Return format is: <proportion of first solution>, <proportion of second solution>, <proportion of water>
        """
        l = max(first, second)  #more concentrated of the two inputs
        lt = max(target1, target2) #greatest of the targets
        s = min(first, second) #less concentrated of the two inputs
        st = min(target1, target2) #smallest of the targets

        if lt > l or st > l:
            return -1, -1, -1

        if st >= s:
            return target1, target2, 0
        else:
            rf = target1 / first
            rs = target2 / second
   
            Rf = (rf)/(rf+rs)
            Rs = (rs)/(rf+rs)
           
            print(rf,rs, Rf, Rs)
            if Rf < rf:
                return 'No Solution'
               
            water = (Rs * second)/target2-1
            total = (Rf+Rs+water)
            return Rf/total,Rs/total, water/total

    def next_water_source(self, required_amount):
        """
        Loop throgh water sources and return first water source with enough water for required amount
        """
        for i, w in enumerate(self.water_sources):
            if w[1]-2 >= required_amount: #-2 to account for unreachable water in vial
                return i, w[0]
        return -1, -1
        

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
        self.goto_safe(rack_source_official_approach[getattr(self.source_rack, source)])
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
    
    def cap_and_return_vial_to_rack(self, dest_id, rack = rack_disp_official):
        """
        Simple helper function for when procedures in the carousel have been completed.
        This function caps the vial, and returns it to its original position.
        Takes in the vial's position on the dispense section of the main rack and returns it there 
        """
        #cap and return to rack
        self.move_carousel(0,0)
        self.close_clamp()
        self.goto_safe(vial_carousel_approach)
        self.cap(torque_thresh = 600)
        self.holding_vial = True
        self.open_clamp()                
        self.goto_safe(rack[dest_id])
        self.open_gripper()
        self.holding_vial = False
        self.move_z(400)
                             
    def move_vial(self, src_loc, dest_loc):
        """
        Move vial between two different locations
        """
        self.goto_safe(src_loc)
        self.close_gripper()
        self.delay(1.5)
        self.goto_safe(dest_loc)
        self.close_clamp()
        self.open_gripper()
        self.delay(0.5)
        self.open_clamp()
            
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

    def map_source_rack(self, csv_path):
        """
        Creates SourceRack object as defined in settings folder. See settings/source_rack.py for details
        Maps using the csv given. csv_path should be a path to a csv file that simulates the source_rack grid and its contents
        """
        df = pd.read_csv(csv_path, header=None)
        df = df.iloc[:, ::-1]
        vials = []
        vols = []
        indexes = []
        i = 0
        for col in df:
            for el in df[col]:
                if el == 'x' or el == 'e': # x to signify robot cannot reach position. e means vial at index is empty 
                    i += 1
                    continue
            
                if len(el.split()) != 2:
                    raise Exception("Each element needs to have 2 items: vial_name and volume")       

                vial, vol = el.split()
                vials.append(vial)
                vols.append(vol)
                indexes.append(i)
                i += 1             
                
        self.source_rack = SourceRack(vials, vols, indexes)

    def map_water_source(self, locs = None, vols = None, csv_path = None):
        """
        Map water sources. Stores a list of water sources. Each source represented by a list - [<index of rack>, <initial volume>] 
        If df_path is given, maps using the df given. df_path should be a path to a csv file that simulates the placement of water vials on the center rack.
        CSV contents should be a grid showing the volume of water in each source vial on the grid.
        e.g. 3 vials each with 8ml water on bottom row is represented as:
        0 0 0
        8 8 8

        0 means no water source at given index
        """
        if csv_path:
            df = pd.read_csv(csv_path, header=None)
            df = df.iloc[:, ::-1]
            res = []
            i = 0
            for col in df:
                for el in df[col]:
                    if el != 0:
                        self.solution_vols[i] = el
                        res.append([i, el])
                    i += 1
            self.water_sources = res
        else:
            locs = locs.split()
            vols = vols.split()

            if len(locs) != len(vols):
                raise Exception("Length of inputs must be equal!")
            
            self.water_sources = [list(t) for t in zip(locs, vols)]