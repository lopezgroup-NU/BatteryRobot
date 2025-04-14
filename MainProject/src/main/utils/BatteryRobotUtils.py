import time
import heapq
from north import NorthC9
from molmass import Formula
import pandas as pd
from Locator import *
from config import SourceRack, HeatRack, DispRack, PowderProtocol
from utils.PStat.geis import *
from utils.PStat.cv import *
from utils.PStat.ocv import *
from .PowderShakerUtils import PowderShaker
from .ExceptionUtils import *
from .CalculationUtils import get_time_stamp
"""
Module for BatteryRobot operation
"""

class BatteryRobot(NorthC9):
    """
    READ DOCS BEFORE USING FUNCTIONS

    child of NorthC9 - inherits North's methods plus methods defined in here
    """

    def __init__(self, address, network_serial, home=False):
        """
        Startup procedures
        """
        super().__init__(address, network_serial=network_serial)
        if home:
            self.home_robot() #Robot arm homing
            self.home_carousel() #Robot carousel homing
            self.reset_pump()
            self.home_pump(3)  #Pipette pump homing
            self.home_pump(0) #Pump system sensing homing
            self.set_pump_valve(3, 0) #Set pump system valve at input position

        self.holding_pipette = False # is arm holding pipette
        self.holding_vial = False # is arm holding cap
        self.cap_holder_1_free = True
        self.cap_holder_2_free = True

        self.cartridge_on_carousel: PowderProtocol = None
        self.cartridge_pos = {
            "LiOAc": 1,
            "default": 2,
            "alconox": 3
        }
        self.pip_id = 0
#sup nerd bye - G, a full grown man and phd student 
        # stores index:volume_remaining for each water source for purging.
        # index in relation to disp_rack
        self.deck_initialized = False
        self.disp_rack = None
        self.source_rack = None
        self.heat_rack = None
        self.res1_vol = 67.2 
        self.res2_vol = 67.2
        self.vol_purge = 19 
        self.water_start = 15

    def run_formulation(self, run_file):
        """
        Takes input file path to a csv containing test details.
        Synthesizes each specified formulation.
        """
        if not self.deck_initialized:
            raise Exception("Initialize deck first! Use initialize_deck()")
        heating_tasks = []
        heapq.heapify(heating_tasks)

        df = pd.read_csv(run_file)

        #start spinner
        self.spin_axis(6, 7000)

        log_file = open("experiments/formulation.log", "a")
        log_file.write("*" * 50 + "\n")
        log_file.write(f"Making formulations: {get_time_stamp()} \n")

        for experiment in df.itertuples():
            try:
                #main experiment body that i escape from when a vial is done heating
                #solids
                has_solids = pd.notna(experiment.Solids)
                has_liquids = pd.notna(experiment.Sources)
                collect = True

                target_pos = experiment.Target_vial
                target_idx = self.disp_rack.pos_to_index(target_pos)
                log_file.write(
                    f"   Start formulation for vial at {target_pos} at: {get_time_stamp()} \n"
                    )

                if has_solids:
                    solid_list = experiment.Solids.split()
                    mass_list = experiment.Weights_g.split()
                    mass_list = [float(mass) for mass in mass_list]

                    if len(solid_list) != len(mass_list):
                        raise ContinuableRuntimeError(
                            f"Experiment {experiment.Experiment}: \
                                Mismatch in solid list and mass list")

                    for i, solid in enumerate(solid_list):
                        mass = mass_list[i]
                        ret = bool((i == len(solid_list) - 1) and (not has_liquids))
                        self.dispense_powder_and_scale(solid, target_idx, mass, collect, ret)
                        collect = False
                #liquids
                if has_liquids:
                    source_list = str(experiment.Sources).split()
                    vol_list = str(experiment.Volumes_mL).split()
                    vol_list = [float(vol) for vol in vol_list]

                    if len(source_list) != len(vol_list):
                        raise ContinuableRuntimeError(f"Experiment {experiment.Experiment}: \
                                                      Length mismatch in source list and vol list ")

                    for i, source_pos in enumerate(source_list):
                        vol = vol_list[i]
                        ret = bool(i == len(source_list) - 1)
                        source_idx = self.source_rack.pos_to_index(source_pos)
                        #updates source rack contents
                        self.dispense_vol(target_idx, source_idx, vol, collect, ret)
                        collect = False
                        #update disp rack contents
                        disp_vial_name = getattr(self.disp_rack, target_pos)
                        current_vol = getattr(self.disp_rack, disp_vial_name + "_vol")
                        self.disp_rack.set_vial_by_pos(target_pos, current_vol + vol)

                #heat and wait for them
                heatplate_pos = experiment.Heat
                heatplate_idx = self.heat_rack.pos_to_index(heatplate_pos)
                heat_time = float(experiment.Time_h) * 3600 # convert to seconds
                self.move_vial(rack_disp_official[target_idx], heatplate_official[heatplate_idx])
                #store in binary heap as tuple - binary heap autosorts everytime you insert
                heapq.heappush(heating_tasks, (time.time()+heat_time, heatplate_idx, target_idx))

            except ContinuableRuntimeError as e:
                response = input(f"{e}. \nError with current formulation. Continue? Yes/No")
                if response.upper() == "YES":
                    continue
                elif response.upper() == "NO":
                    break

            vials_to_remove = True
            while heating_tasks and vials_to_remove:
                if heating_tasks:
                    soonest = heating_tasks[0]
                    time_done = soonest[0]
                    if time_done <= time.time():
                        heated_vial = heapq.heappop(heating_tasks)
                        heatplate_idx, target_idx = heated_vial[1], heated_vial[2]
                        self.move_vial(heatplate_official[heatplate_idx],
                                       rack_disp_official[target_idx])
                        log_file.write(f"   Finished making formulation for vial at position \
                                        {self.disp_rack.index_to_pos(target_idx)}:\
                                        {get_time_stamp()} \n")
                    else:
                        vials_to_remove = False
                else:
                    vials_to_remove = False

        while heating_tasks:
            print("Some vials still heating. Check every 60 seconds to see if any are done")
            soonest = heating_tasks[0] #next vial to be done heating
            time_done = soonest[0]
            if time_done <= time.time():
                heated_vial = heapq.heappop(heating_tasks)
                heatplate_idx, target_idx = heated_vial[1], heated_vial[2]
                self.move_vial(heatplate_official[heatplate_idx], rack_disp_official[target_idx])
                log_file.write(f"   Finished making formulation for vial at position \
                               {self.disp_rack.index_to_pos(target_idx)}:  {get_time_stamp()} \n")

            else: # if soonest vial isn't ready yet, wait 60 seconds
                time.sleep(60)

        log_file.write(f"Finished all formulations: {get_time_stamp()} \n")
        log_file.write("*" * 50 + "\n")
        log_file.close()

        #turn off spinner
        self.spin_axis(6, 0)
        print("Done running!")

    def run_test(self, run_file):
        '''Runs the testing files'''
        df = pd.read_csv(run_file)

        #way to control purge for now
        water_start = 15

        log_file = open("experiments/experiments.log", "a")
        log_file.write("*" * 50 + "\n")
        log_file.write(f"Running tests: {get_time_stamp()} \n")

        for test in df.itertuples():
            try:
                target_pos = test.Reagent
                log_file.write(f"   Beginning tests for position {target_pos} at: \
                               {get_time_stamp()} \n")

                target_idx = self.disp_rack.pos_to_index(test.Reagent)
                GEIS = True if test.GEIS else False
                CV = True if test.CV else False
                CE = True if test.CE else False
                output_file_name = test.Test_Name

                if GEIS and CV:
                    if len(test.GEIS_Conditions.split()) != 3:
                        raise ContinuableRuntimeError("GEIS_CONDITIONS must have 3 parameters!")
                    if len(test.CV_Conditions.split()) != 3:
                        raise ContinuableRuntimeError("CV_CONDITIONS must have 3 parameters!")

                    init_freq, final_freq, amp = [float(i) for i in test.GEIS_Conditions.split()]
                    point1, point2, rate = [float(i) for i in test.CV_Conditions.split()]

                    geis_parameter_list = {
                        "initial_freq": init_freq,
                        "final_freq": final_freq,
                        "ac_current": amp           #AC current amplitude
                    }

                    for i in range(3):
                        self.move_vial(rack_disp_official[target_idx], vial_carousel)
                        self.goto_safe(safe_zone)
                        self.draw_to_sensor(target_idx, viscous=True, special=True)
                        self.set_output(6, False)
                        self.set_output(7, False)
                        self.set_output(8, False)
                        run_geis(output_file_name=output_file_name + \
                                f"_geis{i}", parameter_list=geis_parameter_list)
                        self.draw_sensor1to2(target_idx, viscous=True)
                        self.set_output(6, True)
                        self.set_output(7, True)
                        self.set_output(8, True)
                        ocv = RunOCV_lastV()
                        run_cv2(output_file_name=output_file_name + f"_cv{i}",
                                values=[[ocv, point1, point2, 0],
                                        [rate, rate, rate],
                                        [0.05, 0.05, 0.05],
                                        1,
                                        0.1])
                        self.set_output(6, False)
                        self.set_output(7, False)
                        self.set_output(8, False)

                #find a way to log the CV results in the summaries

                elif GEIS:
                    self.move_vial(rack_disp_official[target_idx], vial_carousel)
                    if len(test.GEIS_Conditions.split()) != 3:
                        raise ContinuableRuntimeError("GEIS_CONDITIONS must have 3 parameters!")
                    init_freq, final_freq, amp = [float(i) for i in test.GEIS_Conditions.split()]

                    geis_parameter_list = {
                        "initial_freq": init_freq,
                        "final_freq": final_freq,
                        "ac_current": amp
                    }
                    self.set_output(6, False)
                    self.set_output(7, False)
                    self.set_output(8, False)
                    self.draw_to_sensor(target_idx, viscous=True, special=True)
                    run_geis(output_file_name=output_file_name + \
                                f"_geis{i}", parameter_list=geis_parameter_list)
                elif CV:
                    self.move_vial(rack_disp_official[target_idx], vial_carousel)
                    if len(test.CV_CONDITIONS.split()) != 3:
                        raise ContinuableRuntimeError("CV_CONDITIONS must have 3 parameters!")

                    # pass point1, pooint2, rate to run_cv2 (cuz idk what theyre supposed to be)
                    point1, point2, rate = [float(i) for i in test.CV_Conditions.split()]
                    self.draw_to_sensor(target_idx, second_sensor=True)
                    self.set_output(6, True)
                    self.set_output(7, True)
                    self.set_output(8, True)
                    ocv = RunOCV_lastV()
                    run_cv2(output_file_name=output_file_name + f"_cv{i}",
                            values=[[ocv, point1, point2, 0],
                                    [rate, rate, rate],
                                    [0.05, 0.05, 0.05],
                                    1,
                                    0.1])
                    self.set_output(6, False)
                    self.set_output(7, False)
                    self.set_output(8, False)

                log_file.write(f"   Finished tests for position {target_pos} at: \
                               {get_time_stamp()} \n")

                self.purge()

            except ContinuableRuntimeError as e:
                response = input(f"{e}. Unable to run current test. Continue with others? Yes/No")
                if response.upper() == "YES":
                    pass
                elif response.upper() == "NO":
                    break

        log_file.write(f"Finished all formulations: {get_time_stamp()} \n")
        log_file.write("*" * 50 + "\n")
        log_file.close()

    def dispense_powder_and_scale(self, protocol, dest_id, mass, collect=False, ret=True):
        """
        dispense powder into specified vial (dest_id)
        """
        self.check_remove_pipette()

        if collect:
            self.move_vial(rack_disp_official[dest_id], vial_carousel)
        else:
            #assumes already holding vial
            self.goto_safe(vial_carousel)

        self.uncap_vial_in_carousel()
        self.move_carousel(68, 77) # carousel moves 68 degrees, 77 mm down

        start = time.time()
        p2 = PowderShaker('C', network=self.network)
        dispensed = p2.cl_pow_dispense(robot=self, mg_target=mass, protocol=protocol)
        t_taken = time.time() - start

        self.delay(1)
        self.move_carousel(0, 0)

        #return to rack or not
        if ret:
            self.cap_and_return_vial_to_rack(dest_id)
        else:
            self.close_clamp()
            self.goto_safe(vial_carousel_approach)
            self.cap(torque_thresh=500)
            self.open_gripper()
            self.open_clamp()
            self.goto_safe(safe_zone)

        data = {}
        data["Vial ID"] = dest_id
        #milligrams
        data["Intended"] = mass
        data["Real"] = dispensed
        data["Time Taken(s)"] = t_taken
        return data

    def dispense_vol(self, dest_id, source_id, target_vol, collect=False, ret=True):
        """
        Dispense {target_vol} ml from vial with id {source_id} into vial with id {dest_id}
        Destination vials are from rack_dispense_official while source_vials are from
        rack_pipette_aspirate respectively (see Locators)
        """
        self.check_remove_pipette()
        self.goto_safe(rack_source_official[source_id])
        cap_holder_id = self.move_cap_to_holder()

        if collect:
            self.move_vial(rack_disp_official[dest_id], vial_carousel)
        else:
            self.goto_safe(vial_carousel)

        self.uncap_vial_in_carousel()
        self.get_pipette()
        self.zero_scale()

        remaining = target_vol
        pos = self.source_rack.index_to_pos(source_id)
        source_name = getattr(self.source_rack, pos)

        if "TFSI" in source_name.upper() or "FSI" in source_name.upper():
             self.set_pump_speed(3, 25)

        while remaining > 0:
            rack = p_asp_high
            curr_vol = getattr(self.source_rack, source_name + "_vol")
            if curr_vol <= 4:
                rack = p_asp_low
            elif curr_vol <= 6:
                rack = p_asp_mid

            amount = min(remaining, 1)
            if amount < 1:
                self.goto_xy_safe(rack[source_id])
                self.aspirate_ml(3, 1 - amount)
            self.goto_safe(rack[source_id])
            self.aspirate_ml(3, amount)
            self.delay(3)
            self.goto_safe(carousel_dispense)
            self.move_pump(3, 0)
            self.delay(3)
            remaining -= amount
            self.source_rack.set_vial_by_pos(pos, curr_vol - amount)
        
        self.set_pump_speed(3, 15)
        dispensed = self.read_steady_scale()
        self.goto_safe(safe_zone)
        self.remove_pipette()

        if ret:
            self.cap_and_return_vial_to_rack(dest_id)
        else:
            self.close_clamp()
            self.goto_safe(vial_carousel_approach)
            self.cap(torque_thresh=500)
            self.open_gripper()
            self.open_clamp()

        self.move_cap_from_holder(source_id, cap_holder_id)

        data = {}
        data["Vial ID"] = dest_id
        data["Intended(ml)"] = target_vol
        data["Real(ml)"] = dispensed
        return data

    def dispense_mass(self, dest_id, source, target_mass,
                             density, collect=False, ret=True):
        """
        Dispense based on target mass
        """
        self.check_remove_pipette()
        self.goto_safe(rack_source_official[getattr(self.source_rack, str(source))])
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

            #get smaller value between 1, and remaining volume to dispense
            amount = min((target_mass - dispensed)/density, 1)
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
            self.cap(torque_thresh=500)
            self.open_gripper()
            self.open_clamp()

        self.move_cap_from_holder(source, cap_holder_id)

        data = {}
        data["Vial ID"] = dest_id
        data["Intended(g)"] = target_mass
        data["Real(g)"] = dispensed
        return data

    def reset_pump(self):
        self.set_pump_speed(0, 15)
        self.set_pump_valve(0, 0)
        self.move_pump(0, 0)

    def pump_helper(self, length=1300, v_in=13, v_out=0, draw=True):
        """
        Helper function to be used when pumping liquids from carousel.
        """
        self.set_pump_speed(0, v_out)
        self.set_pump_valve(0, int(not draw))
        self.move_pump(0, 0)
        self.set_pump_speed(0, v_in)
        self.set_pump_valve(0, int(draw))
        self.move_pump(0, length)
        print("pumped")

    #viscous (29 speed)
    def move_electrolyte(self, n=None, draw=True, length=2000,
                         extra_slow=False, purge=False, viscous=False, light=False):
        """
        If n is specified, pump will pump n times. Else runs indefinitely.

        draw = True by default. when draw is true, syringe draws electrolyte from vial.
        if draw = False, syringe pushes out electrolyte back into vial. (opposite direction)

        5 speed settings: extra_slow for super viscous, purge viscous. medium, light.
        Defaults to medium speed.

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
                self.pump_helper(length=length, v_in=v_in, v_out=v_out, draw=draw)

        else:
            i = 0
            print("Hit Ctrl+C when you want to stop pumping!")
            while True:
                try:
                    i += 1
                    self.pump_helper(length=length, v_in=v_in, v_out=v_out, draw=draw)
                except KeyboardInterrupt:
                    print(i) # print number of pumps
                    break

        self.reset_pump()

    def draw_to_sensor(self, id, second_sensor=False, length=1300,
                       purge=False, viscous=False, light=False, special=False):
        """
        Assume open vial placed between clamps. Draws 5 pumps of electrolyte,
        and moves it to the first sensor by default.
        Set second_sensor = True if you want to draw directly to the second sensor.
        Otherwise draw to sensor 1 first then use draw_sensor1to2() to draw to the second.
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

        # initialize sol_vols within disp_rack object
        self.disp_rack.get_sol_vols()

        # pumping block
        pos = self.disp_rack.index_to_pos(id)
        current_height = self.get_needle_height(pos)
        self.move_carousel(33, current_height)
        self.pump_helper(length=length, v_in=v_in, v_out=v_out)

        # update csv and disprack object
        disp_vial_name = getattr(self.disp_rack, pos)
        current_vol = getattr(self.disp_rack, disp_vial_name + "_vol")
        vol = 0.4 * length/1250 # length 1250 roughly equal to 0.4ml
        self.disp_rack.set_vial_by_pos(pos, current_vol - vol)

        self.move_carousel(0, 0)
        if special:
            self.open_clamp()
            self.move_vial(vial_carousel, rack_disp_official[id])
        else:
            self.cap_and_return_vial_to_rack(id)

        for _ in range(2):
            self.pump_helper(length=length, v_in=v_in, v_out=v_out)

        if second_sensor:
            length = 1200
        else:
            length = 200

        self.pump_helper(length=length, v_in=v_in, v_out=v_out)
        self.reset_pump()

    def draw_sensor1to2(self, purge=False, viscous=False, light=False):
        """
        When column of electrolyte is already at first sensor,
        moves column to second sensor
        """
        v_in = 20 #speed to draw, default to medium speed
        v_out = 0 # speed to push out air

        if purge:
            v_in, v_out = 35, 5
        elif viscous: # 60 seconds per pump
            v_in, v_out = 35, 0
        elif light:
            v_in, v_out = 1, 0

        self.pump_helper(length=1000, v_in=v_in, v_out=v_out)
        self.reset_pump()

    def purge(self, speed=30, rack=rack_disp_official,
              n_pumps=18, length=3000):
        """
        Purge plumbing system using reservoir. 
        Purge 20ml worth
        Length 3000 (full pump) is about 

        """
        #can use reservoir
        if self.res1_vol > self.vol_purge or self.res2_vol > self.vol_purge:
            if self.res1_vol > self.vol_purge:
                self.move_carousel(91, 85)
                self.res1_vol -= self.vol_purge
            else:       
                self.move_carousel(137,85)
                self.res2_vol -= self.vol_purge

            for _ in range(n_pumps):
                self.pump_helper(length=length, speed=speed, v_out=5)
            
            self.move_carousel(0, 0)
        #use water vials
        else:
            for i in range(self.water_start,  self.water_start+3):
                self.move_carousel(0, 0)
                self.move_vial(rack[i], vial_carousel)

                self.uncap_vial_in_carousel()
                self.move_carousel(33, 85) # carousel moves 33 degrees, 85 mm down
                for _ in range(6):
                    self.pump_helper(length=length, v_in=speed, v_out=5)

                self.move_carousel(0, 0)    
                self.cap_and_return_vial_to_rack(i, rack)

                for _ in range(6):
                    self.pump_helper(length=length, v_in=15, v_out=5)
            self.water_start += 3


    def purge_auto(self, desired_vol=4):
        """
        Loop through purge_sources in disp_rack and find
        suitable purge vial with adequate water, then run purge
        """
        purge_vial_found = False
        for i, purge_vial in enumerate(self.disp_rack.purge_sources):
            vol, id, _ = purge_vial
            if vol >= desired_vol:
                purge_vial_found = True
                self.disp_rack.purge_sources[i][0] -= desired_vol
                break

        if not purge_vial_found:
            raise CriticalRuntimeError("Error: No more water left to purge!")

        self.purge(id)

    def get_needle_height(self, pos):
        vol = self.disp_rack.sol_vols[pos]

        if vol <= 5:
            return 85
        elif vol <= 6:
            return 75
        elif vol <= 7:
            return 70
        else:
            return 65

    def get_new_cartridge(self, new):
        """
        Replace cartridge on carousel (active cartridge) with {new},
        where {new} is a protocol for a powder

        E.g. get_new_cartridge(LiOAc) replaces the active cartridge
        (if present) with the LiOAc cartridge

        Defined protocols can be found in settings/powder_protocols.py
        """
        #position carousel first
        self.move_carousel(68, 77)
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
        self.move_carousel(0, 0)

    def get_pip_height(self, vial):
        """
        Return appropriate pipette height given target solution to draw from.
        Make sure solution name is identical to one in source_rack.csv
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

    def calc_liquid_mol(self, mol, gram, mol_mass):
        """
        Calculates how much liquid to dispense to get a certain Molarity
        """
        liquid_amount = gram/(mol_mass*mol)
        return liquid_amount

    def gram_to_mol(self, solutes: list, solvent_vol: float):
        """
        Given mass of solutes in grams and solvent volume, return concentration of each solute
        solutes is a list of tuples - [(solute1, mass1), (solute2, mass2)] - where soluteX is
        the chemical formula of the solute
        """
        mols = []

        for solute, mass in solutes:
            mol_mass = Formula(solute).mass
            mol = mass/mol_mass
            mols.append((solute, mol/solvent_vol))

        return mols

    def move_cap_to_holder(self):
        """
        Helper function to move cap to a free cap holder.
        Assumes gripper is at target vial's cap's location
        """
        self.close_gripper()
        self.delay(.5)
        self.uncap(revs=4)

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

        self.cap(revs=3, torque_thresh=400)
        self.open_gripper()
        self.delay(.5)
        return cap_holder_id

    def move_cap_from_holder(self, source_id, cap_holder_id):
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
        self.uncap(revs=3.5)
        self.goto_safe(rack_source_official_approach[source_id])
        self.cap(revs=3, torque_thresh=400)
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

    def cap_and_return_vial_to_rack(self, dest_id, rack=rack_disp_official):
        """
        Simple helper function for when procedures in the carousel have been completed.
        This function takes in the vial's index and a given rack, caps the vial, and moves it
        to the specified rack's index.
        """
        #cap and return to rack
        self.move_carousel(0, 0)
        self.close_clamp()
        self.goto_safe(vial_carousel_approach)
        self.cap( revs = 2, torque_thresh=500)
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
        gets new pipette at specified position {pip_index} from pipette rack.
        Will throw an error if robot is holding a vial.
        Pipette rack is indexed as follows:
          47 ...... 8 5 2
          46 ...... 7 4 1
          45 ...... 6 3 0
        By default, robot takes pipette from index 0 (bottom right corner as shown above)
        """
        # Checks if robot is currently holding a vial
        if self.holding_vial:
            raise Exception("Holding vial! Unsafe to perform pipette operations")

        pipette_order = list(range(2, 48, 3)) + \
                        list(range(1, 48, 3)) + \
                        list(range(0, 48, 3))

        print(f"getting pipette at index {self.pip_id}")
        self.goto_safe(pipette_grid[pipette_order[self.pip_id]])
        self.increment_pip_id()
        self.move_z(400, vel=10) # lift up before moving to safe spot
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

    def initialize_deck(self, disp_rack_path, source_rack_path, heat_rack_path):
        """
        Initialize deck by mapping rack contents
        """
        try:
            self.disp_rack = DispRack(disp_rack_path)
            self.source_rack = SourceRack(source_rack_path)
            self.heat_rack = HeatRack(heat_rack_path)
            self.deck_initialized = True
        except InitializationError as e:
            print(e)
            print("Fix the rack csvs and try again.")