import time
import heapq
import yaml
import datetime
import pandas as pd
import tkinter as tk
import threading
import uuid
from GUI import *
from north import NorthC9
from molmass import Formula
from Locator import *
from config import SourceRack, HeatRack, DispRack, PowderProtocol
from datetime import datetime as dt
from utils.PStat.peis import *
from utils.PStat.geis import *
from utils.PStat.cv import *
# from utils.PStat.cp import *
from utils.PStat.ca import *
from utils.PStat.triplet import *
from utils.PStat.new_db import *

from utils.PStat.ocv import *
from utils.mouseUtils import *
from utils.PAGUtils import *
from utils.PowderShakerUtils import PowderShaker
from utils.T8Utils import T8
from utils.ExceptionUtils import *
from utils.MathUtils import get_time_stamp


"""
Module for BatteryRobot operation
"""

class BatteryRobot(NorthC9):
    """
    READ DOCS BEFORE USING FUNCTIONS

    child of NorthC9 - inherits North's methods plus methods defined in here
    """
    Global_Plate = None
    

    # NOTE: PROPERTIES FOR PLATE_ID FILE SYSTEM. THESE ARE GLOBAL VARIABLES
    Plate_Properties = {}

    ACTIVE_TESTS = ["PEIS", "CV"]

    def __init__(self, address, network_serial, home=False, config_path = "config/config.yaml"):
        """
        Startup procedures
        setup_gui will prompt user to check on disp and source rack csvs. Set to false for closed loop, so that robot doesnt get blocked
        """
        super().__init__(address, network_serial=network_serial)

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        hw_states = self.config.get("hardware_states", {})
        self.holding_pipette = hw_states.get("holding_pipette", False)  # is arm holding pipette
        self.holding_vial = hw_states.get("holding_vial", False)  # is arm holding cap
        self.cap_holder_1_free = hw_states.get("cap_holder_1_free", True) # is cap holder 1 free
        self.cap_holder_2_free = hw_states.get("cap_holder_2_free", True) 
        self.pip_id = hw_states.get("pip_id", 0) 

        carousel_config = self.config.get("carousel", {})
        self.cartridge_on_carousel = None
        self.cartridge_pos = carousel_config.get("cartridge_positions", {
            "LiOAc": 1,
            "default": 2,
            "alconox": 3
        })

        rack_files = self.config.get("racks", {})

        disp_rack_filename =  rack_files.get("disp_rack")
        source_rack_filename =  rack_files.get("source_rack")

        self.initialize_deck(
            disp_rack_filename,
            source_rack_filename,
            rack_files.get("heat_rack"),
            rack_files.get("heat_rack2")
        )
        resources = self.config.get("resources", {})
        self.res1_vol = resources.get("res1_vol", 67.2)
        self.res2_vol = resources.get("res2_vol", 67.2)
        self.vol_purge = resources.get("vol_purge", 19)
        self.water_start = resources.get("water_start", 18)
        self.water_end = resources.get("water_end", 47)

        #home before we do anything
        if home:
            self.home_robot() #Robot arm homing
            self.home_carousel() #Robot carousel homing
            self.reset_pump()
            self.home_pump(3)  #Pipette pump homing
            self.home_pump(0) #Pump system sensing homing
            self.set_pump_valve(3, 0) #Set pump system valve at input position

    def prompt_user_check_conditions(self, conditions):
        """
        Run a demo for the class which is visiting the lab on November 11th
        """

        print("Enter a '1' for each of the following if true, and a '0' if false")

        count_conditions_fulfilled = 0
        all_conditions_fulfilled = False
        failed_conditions = []

        while not all_conditions_fulfilled:

            for condition in conditions:
                cond = input(conditions[condition])
                if cond == '1':
                    count_conditions_fulfilled += 1
                elif cond == '0':
                    failed_conditions.append(conditions[condition])
                else:
                    print("That isn't a valid response. Make sure there are no spaces or anything, then press enter")
                    condition -= 1

            if count_conditions_fulfilled == len(conditions):
                all_conditions_fulfilled = True
            else:
                print("Not all condiitons are fulfilled. Please ensure that everything is in order and try again")
                print("")
        print("All conditions are fulfilled. Starting the program in 1 second!")
        self.delay(1)

        dispense_vial_prepared = input("Put a vial half-full of H2O, with a special cap (green w/ hole in middle) in the A1 position of the dispense rack. Type 1 once completed:  ")
        source_vial_prepared = input("Put a vial full of H2O in the B4 position of the source rack. Type 1 once completed:  ")
        carousel_is_empty = input("Remove any vial currently in the vial clamp.  Type 1 once completed:  ")
        heat_rack_empty = input("Remove all vials from the heating rack. Type 1 once completed:  ")

        if dispense_vial_prepared == '1' and source_vial_prepared == '1' and carousel_is_empty == '1' and heat_rack_empty  == '1':
            print("All conditions are fulfilled. Starting the program now!")
            self.delay(2.5)

    def run_formulation(self, run_file):
        """
        Takes input file path to a csv containing test details.
        Synthesizes each specified formulation.
        """
        heating_tasks = []
        heapq.heapify(heating_tasks)
        df = pd.read_csv(run_file)

        #start spinner and heat
        t8 = T8('B', network = self.network)
        
        # turns on spinners and heaters
        self.spin_axis(6, 7000)
        self.spin_axis(7, 7000)
        t8.set_temp(0, 50)
        t8.set_temp(1, 50)


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
                if not pd.isna(experiment.Heat) and str(experiment.Heat).strip():
                    heatrack_pos = experiment.Heat
                    heatrack_idx, heatrack_num = self.heat_rack.pos_to_index(heatrack_pos)
                    if heatrack_num == 1:
                        heatrack = heatplate_official
                    elif heatrack_num == 2:
                        heatrack = heatplate_official2
                    heat_time = float(experiment.Time_h) * 3600 # convert to seconds
                    self.move_vial(rack_disp_official[target_idx], heatrack[heatrack_idx])
                    #store in binary heap as tuple - binary heap autosorts everytime you insert
                    heapq.heappush(heating_tasks, (time.time()+heat_time, heatrack_idx, heatrack, target_idx))

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
                        heatrack_idx, heatrack, target_idx = heated_vial[1], heated_vial[2], heated_vial[3]
                        self.move_vial(heatrack[heatrack_idx],
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
                heatrack_idx, heatrack, target_idx = heated_vial[1], heated_vial[2], heated_vial[3]
                self.move_vial(heatrack[heatrack_idx], rack_disp_official[target_idx])
                log_file.write(f"   Finished making formulation for vial at position \
                               {self.disp_rack.index_to_pos(target_idx)}:  {get_time_stamp()} \n")

            else: # if soonest vial isn't ready yet, wait 60 seconds
                time.sleep(60)

        log_file.write(f"Finished all formulations: {get_time_stamp()} \n")
        log_file.write("*" * 50 + "\n")
        log_file.close()

        #turn off spinner and heat
        self.spin_axis(6, 0)
        self.spin_axis(7, 0)
        t8.set_temp(0, 10)
        t8.set_temp(1, 10)
        print("Done running!")

    def run_test(self, run_file, standard = None, g_mode = True): # NOTE: pumping is very slow; carousel rotates too much (overshoots) off center of bottle cap
        '''
        Runs the testing files
        If standard is provided, will run experiment before and after test file is done
        Standard should be a dict consisting of the standard's name (default to "standard") 
        and the position it is located. e.g.
 
        standard = {
            "name": "standard",
            "pos": "B5",
            "electrode_used": "Pt"
        }
 
        '''
        import uuid
        import toolkitpy as tkp
        if not getattr(tkp, "_init_done", False):
            tkp.toolkitpy_init("run_test.py")
            tkp._init_done = True
            tkp.toolkitpy_init = lambda *a, **k: None
 
        today = dt.now()
        formatted_date = today.strftime("%Y%m%d_%H%M%S")  # YearMonthDay_HourMinuteSecond
        
        granular_log_file = open(f"C:/AttomRobotFiles/Software/BatteryRobot/MainProject/src/main/granular_logs/test_{formatted_date}.txt", "a", buffering=1)
        # granular_log_file = open(f"C:/AttomRobotFiles/Software/BatteryRobot/MainProject/src/main/granular_logs/test_{formatted_date}.txt", "a")        
 
        summary_path = r"C:\AttomRobotFiles\Software\BatteryRobot\MainProject\src\main\res\data_summary.csv"

        # 


        # def record_run(test_id, run_id, run_type: str, order):
        #     import os
        #     new_row = pd.DataFrame([{
        #         "id": test_id,
        #         "run_id": run_id,
        #         "order": order,
        #         "electrode": electrode_used,
        #         "formulation": getattr(test, "Experiment", ""),
        #         "run_type": run_type,
        #     }])
        #     write_header = not os.path.exists(summary_path)
        #     new_row.to_csv(summary_path, mode="a", header=write_header, index=False)
 
        # def record_run(test_id, run_id, run_type: str, order):
        #     import os
        #     sub = ("res/standard/" if row_is_standard else "res/") + \
        #           ("geis/" if run_type == "GEIS" else "cv/")
        #     new_row = pd.DataFrame([{
        #         "id": test_id, "run_id": run_id, "order": order,
        #         "electrode": electrode_used,
        #         "formulation": getattr(test, "Experiment", ""),
        #         "run_type": run_type,
        #         "standard": row_is_standard,
        #         "path": os.path.abspath(sub + test_id + ".csv"),
        #         "time": get_time_stamp(),
        #     }])
        #     write_header = not os.path.exists(summary_path)
        #     new_row.to_csv(summary_path, mode="a", header=write_header, index=False)

        summary = SummaryCSV(DATA_SUMMARY)

        def record_run(test_id, run_id, run_type: str, order):
            import os
            exp = str(getattr(test, "Experiment", ""))
            comps = parse_formulation(exp)
            sub = "res/" + ("geis/" if run_type == "GEIS" else "cv/")
            fpath = os.path.abspath(sub + test_id + ".csv")
            summary.append(TestRecord(
                id=test_id, run_id=run_id,
                formulation=canonical_formulation(comps) or exp,  # LiTFSI_1p50m -> LiTFSI_1p5m; plain names pass through
                run_type=run_type, order=order,
                electrode=str(electrode_used),
                date=get_time_stamp(),
                temp=read_temp(fpath),
                notes=str(getattr(test, "Notes", "")),
                path=fpath,
                components=comps,
            ))


        df = pd.read_csv(run_file)
        self.disp_rack.get_sol_vols()
        missing = [p for p in df["Target_vial"] if p not in self.disp_rack.sol_vols]
        if missing:
            raise Exception("Target vials missing from disp_rack.csv (name/volume): {}".format(missing))
        run_standard = standard is not None
        if run_standard:
            # perform checks on disp rack and ensure vial has been added. 
            name = standard.get("name", "standard")
            try:
                pos = standard.get("pos")
            except:
                raise Exception("Need to provide a pos for standard!")
            
            tup = self.disp_rack.get_vial_by_pos(pos)
            if tup is None:
                raise Exception("Add standard vial to disp_rack.csv first!")
 
            if tup[0] != name:
                raise Exception(f"Make sure vial name at {pos} on disp_rack.csv is the same \
                                as what you provide to run_test()")
            
            
            name = name + "_" + formatted_date
            std = {"Experiment": name, "Target_vial": pos,
                   "electrode_used": standard.get("electrode_used"),
                   "GEIS": True, "GEIS_Conditions": "250000 1 0.00001",
                   "CV": True, "CV_Conditions": "2 -2 0.020",
                   "CE": False, "SaveDB": False}
            missing = set(df.columns) - set(std)
            if missing:
                raise Exception(f"Standard row missing columns: {missing}")
            new_row = pd.DataFrame([std])[df.columns]
            df = pd.concat([new_row, df, new_row], ignore_index=True)
            # row = [name, pos, standard.get("electrode_used"),True, "250000 1 0.00001", True, "2 -2 0.020", False, False]
            # new_row = pd.DataFrame([row], columns=df.columns)
            # df = pd.concat([new_row, df, new_row], ignore_index=True)
 
        log_file = open("experiments/experiments.log", "a")
        log_file.write("*" * 50 + "\n")
        log_file.write(f"Running tests: {get_time_stamp()} \n")
 
        for i, test in enumerate(df.itertuples()):
            try:
                print(test)
                target_pos = test.Target_vial
                electrode_used=test.electrode_used
                log_file.write(f"   Beginning tests for position {target_pos} at: \
                               {get_time_stamp()} \n")
 
                target_idx = self.disp_rack.pos_to_index(target_pos)
                GEIS = True if test.GEIS else False
                CV = True if test.CV else False
                CE = True if test.CE else False
                run_id = uuid.uuid4().hex 

                save_to_db = test.SaveDB
                row_is_standard = run_standard and (i == 0 or i==len(df) - 1)
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
 
                    # this test is a standard test if we determine we're running a standard
                    # and this is the first or last row of the run
                    geis_files = []
                    cv_files = []
                    # run test three times
                    for j in range(3):
                        test_id_geis = uuid.uuid4().hex
 
                        self.move_vial(rack_disp_official[target_idx], vial_carousel)
                        granular_log_file.write(f"\n * moved vial from index {target_idx} to carousel" + f" *** {get_time_stamp()}")
                        self.goto_safe(safe_zone)
                        granular_log_file.write(f"\n * moved arm to safe zone" + f" *** {get_time_stamp()}")
                        self.draw_to_sensor(target_idx, viscous=True, special=True)
                        granular_log_file.write(f"\n * drew from carousel vial to sensor 1" + f" *** {get_time_stamp()}")
                        self.set_output(6, False)
                        self.set_output(7, False)
                        self.set_output(8, False)
                        
                        run_geis(output_file_name=test_id_geis,
                                parameter_list=geis_parameter_list, 
                                save_to_db_folder = save_to_db,
                                standard=row_is_standard)
                        granular_log_file.write(f"\n * ran geis test" + f" *** {get_time_stamp()}")
                        # geis_files.append(geis_file)
                        record_run(test_id_geis, run_id, "GEIS", j)
                        self.draw_sensor1to2(viscous=True)

                        # self.draw_sensor1to2(target_idx, viscous=True)
                        granular_log_file.write(f"\n * drew from carousel vial to sensor 2 (from sensor 1)" + f" *** {get_time_stamp()}")
                        self.set_output(6, True)
                        self.set_output(7, True)
                        self.set_output(8, True)
                        ocv = RunOCV_lastV()
                        print("running cv test")
                        test_id_cv = uuid.uuid4().hex
                        run_cv_output(output_file_name=test_id_cv,
                                values=[[ocv, point1, point2, 0],
                                        [rate, rate, rate],
                                        [0.05, 0.05, 0.05],
                                        1,
                                        0.1], 
                                electrode_used = electrode_used,
                                save_to_db_folder = save_to_db,
                                standard=row_is_standard)
                        granular_log_file.write(f"\n * ran cv test" + f" *** {get_time_stamp()}")
                        # cv_files.append(cv_file)
                        self.set_output(6, False)
                        self.set_output(7, False)
                        self.set_output(8, False)
 
                        record_run(test_id_cv, run_id, "CV", j)
 
                    if save_to_db:
                        pass
 
                elif GEIS:
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
                    for j in range(3):
                        test_id = uuid.uuid4().hex
                        self.move_vial(rack_disp_official[target_idx], vial_carousel)
                        granular_log_file.write(f"\n * moved vial from index {target_idx} to carousel" + f" *** {get_time_stamp()}")
                        self.goto_safe(safe_zone)
                        granular_log_file.write(f"\n * moved arm to safe zone" + f" *** {get_time_stamp()}")
                        self.draw_to_sensor(target_idx, viscous=True, special=True)
                        granular_log_file.write(f"\n * drew from carousel vial to sensor 1" + f" *** {get_time_stamp()}")
                        run_geis(output_file_name=f"{test_id}",
                                 parameter_list=geis_parameter_list,
                                save_to_db_folder = save_to_db,
                                standard=row_is_standard)
                        granular_log_file.write(f"\n * ran geis test" + f" *** {get_time_stamp()}")
                        record_run(test_id, run_id, "GEIS", j)
                elif CV:
                    if len(test.CV_CONDITIONS.split()) != 3:
                        raise ContinuableRuntimeError("CV_CONDITIONS must have 3 parameters!")
                    # pass point1, pooint2, rate to run_cv2 
                    point1, point2, rate = [float(i) for i in test.CV_Conditions.split()]
 
                    self.set_output(6, True)
                    self.set_output(7, True)
                    self.set_output(8, True)
                    for j in range(3):
                        test_id = uuid.uuid4().hex
                        self.move_vial(rack_disp_official[target_idx], vial_carousel)
                        granular_log_file.write(f"\n * moved vial from index {target_idx} to carousel" + f" *** {get_time_stamp()}")
                        self.draw_to_sensor(target_idx, second_sensor=True)
                        granular_log_file.write(f"\n * drew from carousel vial to sensor 1" + f" *** {get_time_stamp()}")
                        ocv = RunOCV_lastV()
                        run_cv_output(output_file_name=test_id,
                                values=[[ocv, point1, point2, 0],
                                        [rate, rate, rate],
                                        [0.05, 0.05, 0.05],
                                        1,
                                        0.1],
                                electrode_used = electrode_used,
                                save_to_db_folder = save_to_db,
                                standard=row_is_standard)
                        granular_log_file.write(f"\n * ran cv test" + f" *** {get_time_stamp()}")
                        record_run(test_id, run_id, "CV", j)
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
        granular_log_file.close()

    def runs_to_official(self, 
                   staging_dir = Path(r"C:\AttomRobotFiles\Software\BatteryRobot\MainProject\src\main\res\DB_upsert_G"), 
                   data_summary = Path(r"C:\AttomRobotFiles\Software\BatteryRobot\MainProject\src\main\res\data_summary.csv"), 
                   db_root = Path(r"C:\AttomRobotFiles\Data\DB_Missaka"),
                   official = Path(r"C:\AttomRobotFiles\Data\DB_Missaka\official_summary.csv"), 
                   move = False):
        promote_folder(staging_dir, data_summary, db_root, official, move)


    def runs_to_DB(self,
                   official = Path(r"C:\AttomRobotFiles\Data\DB_Missaka\official_summary.csv"), 
                   uri = "mongodb://localhost:27017/",
                   db_name = "G_updated",
                   coll_name = "formulations"):
        upload_official_to_mongo(official, uri, db_name, coll_name)

    def translate_coords_to_index(self, coords):
        """
        takes in coords like "A2"
        """

        coords = coords.upper()
        letter_index = 0
        if coords[0] == 'A':
            letter_index = 0
        elif coords[0] == 'B':
            letter_index = 1
        elif coords[0] == 'C':
            letter_index = 2
        elif coords[0] == 'D':
            letter_index = 3

        index = 4*(coords[1]-1) + letter_index

    def dispense_into_well(self, reservoir_id, well, mL_to_fill):
        self.open_gripper()
        self.reset_pump()


        #source = disp_rack_id
        #wells_to_fill = well
        mL_remaining = mL_to_fill

        #move vial to the carousel, uncap it, and get pipette
        self.get_pipette()
        self.zero_scale()

        while mL_remaining > 0:
        # draw from the vial in the carousel and dispense it at the well plate
            self.goto_safe(carousel_aspirate)
            mL_to_dispense_this_cycle = min(1, mL_remaining)
            self.aspirate_ml(3, mL_to_dispense_this_cycle)
            mL_remaining -= mL_to_dispense_this_cycle

            #TODO Enter code in here to go to the "well" position in ciara's well plate thing
            
            self.dispense_ml(3, mL_to_dispense_this_cycle)
            
            #TODO Enter code in here to leave the well plate. maybe a goto_safe(safe_zone)

    def get_xyz_position(self):
        pos_cts = self.get_robot_positions()
        pos_xyz = list(self.n9_fk(pos_cts[0], pos_cts[1], pos_cts[2]))
        pos_xyz.pop()
        z = self.counts_to_mm(3, pos_cts[3])
        pos_xyz.append(z)
        print(pos_xyz)
        return pos_xyz
    
    def set_pos_manual(self):
        self.home_robot()
        self.robot_servo(False)

        input("Position Arm. Enter to set desired position")

        captured_position = self.get_robot_positions()

        input("Press Enter to test saved position")
        self.home_robot()
        self.goto_safe(captured_position)
        print(captured_position)

    def star_dropcast(self, position, volume = 0.5, pump_id = 3):
        self.goto_safe(position)

        pos_cts = self.get_robot_positions()
        pos_xyz = list(self.n9_fk(pos_cts[0], pos_cts[1], pos_cts[2]))
        pos_xyz.pop()
        z = self.counts_to_mm(3, pos_cts[3])
        pos_xyz.append(z)
        print(pos_xyz)
        #pos_xyz = [66,70,285]
        squish_factor = 0.6
        r = 4
        circle_points = []
        num_steps = 12
        for index in range(0,num_steps//2):
            theta = ((index/(num_steps//2)) * 2*math.pi) + math.pi/2
            circle_points.append([r*math.cos(theta), r*math.sin(theta)*squish_factor])
        
            theta = ((index/(num_steps//2)) * 2*math.pi) + math.pi/2
            circle_points.append([-1*r*math.cos(theta), r*math.sin(theta)*squish_factor])
        #circle_points.append([-1*r, 0])
        #circle_points.append([r, 0])
        # if len(circle_points) % 4 != 0:
        #     for i in range(len(circle_points) % 4):
        #         circle_points.pop()
        dispense_steps = num_steps + 1
        print(circle_points)
        print(len(circle_points))
        for i in range(0, num_steps//2):
            circle_points[i][1] += r*squish_factor
            circle_points[i+int((len(circle_points)/2))][1] -= r*squish_factor
        already_dispensed_coords = []

        for coord in circle_points:
            if [round(coord[0],1), round(coord[1],1)] not in already_dispensed_coords:
                print(f"{ coord[0]}\t{coord[1]}")
                self.move_xy(pos_xyz[0] + coord[0], pos_xyz[1] + coord[1])
                self.delay(0.1)
                self.dispense_ml(pump_id, volume/(dispense_steps))
                already_dispensed_coords.append([round(coord[0],1), round(coord[1],1)])
        self.move_xy(pos_xyz[0] + (r*2), pos_xyz[1])
        self.delay(0.1)
        self.dispense_ml(pump_id, volume/(dispense_steps))

        self.move_xy(pos_xyz[0] - (r*1.8), pos_xyz[1])
        self.delay(0.1)
        self.dispense_ml(pump_id, volume/(dispense_steps))
        self.delay(1)
        self.goto_safe(dropcast_aspirate)
        self.home_pump(pump_id)
            #self.pump_helper(length=1250/num_steps, draw=True, pump_address=3,suppress=True) 

    def star_dropcast_prep(self, pump_id = 3, empty_pipette = False):
        self.home_pump(pump_id)
        self.goto_safe(dropcast_aspirate)
        self.set_pump_valve(pump_id, self.PUMP_VALVE_LEFT)
        if empty_pipette:
            self.aspirate_ml(pump_id, 0.5)
            self.dispense_ml(pump_id, 0.5)

    def star_dropcast_cleanup(self, pump_id = 3):
        self.home_pump(pump_id)

    def put_vial_back_from_carousel(self, original_position):

        # remove pipette and cap and return vial
        self.remove_pipette()
        self.cap_and_return_vial_to_rack(original_position)

    def run_cell_tests(self, cell_triplet_seeds, source, mL_to_dispense, cp_amps, test_run = True):
        """
        Docstring for run_cell_tests
        
        :param self: Description
        :param cell_triplet_seeds: list of "seeds" from 0-7 which correspond to triplets with the form [[0,8,16],[1,9,17],[2,10,18], ...]
        :param source: reservoir index which can be drawn from
        :param mL_to_dispense: mL to dispense into each cell
        """

        plate_id = "PLATE" + ''.join(random.choices(string.hexdigits()[:16], k=16))

        id_0 = ''.join(random.choices(string.hexdigits()[:16], k=8))
        id_1 = ''.join(random.choices(string.hexdigits()[:16], k=8))
        id_2 = ''.join(random.choices(string.hexdigits()[:16], k=8))
        cell_triplets = []

        for seed in cell_triplet_seeds:
            cell_triplets.append([seed, seed+8, seed+16])

        past_cell_triplets = []
        for triplet_index in range(source,len(cell_triplets)): #for each triplet
             # for the first (dispensing) action with the triplets, begin running test 1 (geis) immediately
            self.dispense_into_well(source, cell_triplets[triplet_index][0], mL_to_dispense)
            t0 = threading.Thread(target=run_geis_cell, args=(cell_triplets[triplet_index][0], f"ID_{id_0}_EIS.csv")) #saves data; eval statements
            t0.start()
            self.dispense_into_well(source, cell_triplets[triplet_index][1], mL_to_dispense)
            t1 = threading.Thread(target=run_geis_cell, args=(cell_triplets[triplet_index][1], f"ID_{id_1}_EIS.csv"))
            t1.start()
            self.dispense_into_well(source, cell_triplets[triplet_index][2], mL_to_dispense)
            t2 = threading.Thread(target=run_geis_cell, args=(cell_triplets[triplet_index][2], f"ID_{id_2}_EIS.csv"))
            t2.start()
            #join the threads started in the eval statements above
            t0.join()
            t1.join()
            t2.join()

            #run cv
            t0 = threading.Thread(target=run_cv_cell, args=(cell_triplets[triplet_index][0], f"ID_{id_0}_CV.csv"))
            t0.start()
            t1 = threading.Thread(target=run_cv_cell, args=(cell_triplets[triplet_index][1], f"ID_{id_1}_CV.csv"))
            t1.start()
            t2 = threading.Thread(target=run_cv_cell, args=(cell_triplets[triplet_index][2], f"ID_{id_2}_CV.csv"))
            t2.start()
            t0.join()
            t1.join()
            t2.join()
            
            #run cp
            t0 = threading.Thread(target=run_cp_cell, args=(cell_triplets[triplet_index][0], cp_amps, 600, f"ID_{id_0}_CP.csv"))
            t0.start()
            t1 = threading.Thread(target=run_cp_cell, args=(cell_triplets[triplet_index][1], cp_amps, 600, f"ID_{id_1}_CP.csv"))
            t1.start()
            t2 = threading.Thread(target=run_cp_cell, args=(cell_triplets[triplet_index][2], cp_amps, 600, f"ID_{id_2}_CP.csv")) 
            t2.start()
            t0.join()
            t1.join()
            t2.join()
            
            
            for past_cell_triplet in past_cell_triplets:
                #run cp again on all 3 for 1 minute/60 seconds
                t1 = threading.Thread(target=run_cp_cell, args=(past_cell_triplet[0], cp_amps, 60))
                t1.start()
                t2 = threading.Thread(target=run_cp_cell, args=(past_cell_triplet[1], cp_amps, 60))
                t2.start()
                t3 = threading.Thread(target=run_cp_cell, args=(past_cell_triplet[2], cp_amps, 60))
                t3.start()

                t1.join()
                t2.join()
                t3.join()
            

            past_cell_triplets.append(cell_triplets[triplet_index])

        for past_cell_triplet in past_cell_triplets:
            #run cp again on all 3 for 1 minute/60 seconds
            t1 = threading.Thread(target=run_cp_cell, args=(past_cell_triplet[0], cp_amps, 60))
            t1.start()
            t2 = threading.Thread(target=run_cp_cell, args=(past_cell_triplet[1], cp_amps, 60))
            t2.start()
            t3 = threading.Thread(target=run_cp_cell, args=(past_cell_triplet[2], cp_amps, 60))
            t3.start()

            t1.join()
            t2.join()
            t3.join()

    def run_cell_tests_single(self, cell, source=0, mL_to_dispense=0, cp_amps=0):
        """
        Docstring for run_cell_tests
        
        :param self: Description
        :param cell_triplet_seeds: list of "seeds" from 0-7 which correspond to triplets with the form [[0,8,16],[1,9,17],[2,10,18], ...]
        :param source: reservoir index which can be drawn from
        :param mL_to_dispense: mL to dispense into each cell
        """

        
        #self.dispense_into_well(source, cell, mL_to_dispense)
        run_geis_cell(cell)
        
           
        #run cv
        # t0 = threading.Thread(target=run_cv_cell, args=(cell))
        # t0.start()
        # t0.join()
        
        # #run cp
        # t0 = threading.Thread(target=run_cp_cell, args=(cell, cp_amps, 600))
        # t0.start()
        # t0.join()

    def run_triple_cell(self):
        # triplet_test();  
        pass
        
    def runGeisCell(self, cell):
        run_geis_cell(cell, output_file_name=f"cell_{cell}_eis")

    def runPeisCell(self, cell):
        run_peis_cell(cell, output_file_name=f"cell_{cell + 1000}_peis")


    def runCVCell(self, cell):
        # now = datetime.now()
        run_cv_cell(cell, output_file_name=f"cell_{cell+100}_cv")

    def runCACell(self, cell):
        # now = datetime.now()
        run_ca_cell(cell, voltage = 1, time_run = 30, output_file_name=f"cell_{cell+100}_ca")

    def set_tests_list(self, *names):
        set_tests(*names)

    def create_new_plate(self):
        self.Plate_Properties = plate_inputs()
        print("The following inputs are for the SAMPLE LOG file (added to the sample_log.csv)")
        operator = input("Operator: ")
        hypothesis = input("Hypothesis: ")
        notes = input("Notes: ")
        self.Global_Plate = createPlate(config_notes = {"operator" : operator, "hypothesis" : hypothesis, "notes" : notes})

    def new_plate(self):
        from GUI.triplet_gui import new_plate
        self.plate = new_plate()
        return self.plate


    def run_tests_new(self, row, column):
        run_test_cell(self.Global_Plate, row, column, self.Plate_Properties)

    def pstat_mux_test(self):

        cell = 23

        tkp.toolkitpy_init('chrono.py')
        pstat_list_names = tkp.enum_sections()
        print(pstat_list_names)
        """
        pstat_iter = 0
        while pstat_iter < len(pstat_list_names):
            print(pstat_list_names[pstat_iter][0:3])
            if pstat_list_names[pstat_iter][0:3] == 'IFC':
                pstat_list_names.pop(pstat_iter)
                pstat_iter = 0
            pstat_iter+=1
        print(pstat_list_names)
        """
        imx_list = []
        pstat_list = []

        for device_name in pstat_list_names:
            tag = device_name[0:3]
            if tag == 'IMX':
                imx_list.append(device_name)
            elif tag == 'IFC':
                pstat_list.append(device_name)
            else:
                print(f"!!!!! Found a non IMX or IFC type device. It is called: {device_name}")
        
        imx_list.sort()
        pstat_list.sort()

        mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
        print(imx_list)
        print(pstat_list)

        #example_cp_test(8)
        #run_cp_cell(0)
        #
        #run_geis_cell(8)
        #pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])
        # mux = tkp.IMX("IMX", imx_list[0])
        # mux.open()
        # #mux.set_cell(0)
        # mux.set_dac(0, 1.1)
        # mux.set_off_mode(0,tkp.MUX_CELL_LOCAL)
        # mux.set_off_mode(1,tkp.MUX_CELL_LOCAL)
        # #mux.set_off_mode(2,tkp.MUX_CELL_LOCAL)
        # mux.set_dac(0, 1.1)
        # time.sleep(2)
        # mux.close()
        # time.sleep(1)

        #run_cv_cell(1, potentials_to_hold=[[0,1.38]])
        
        #mux.set_dac(1, 1.1)
        #mux.set_dac(2, 1.1)
        # print(mux.dac(0))
        # time.sleep(1)
        # print(mux.dac(0))
        # time.sleep(1)
        # print(mux.dac(0))
        # time.sleep(1)
        # print(mux.dac(3))
        # time.sleep(1)
        # print("done")

        #print(imx_list)
        print(mux_pstat_index)
        #mux.close()

        
        #mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
        #mux.open()

        #mux.set_cell(0)
        #run_cv_cell(0, "simultest0",  [[0, 3, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1])
        """ THIS WORKS
        t0 = threading.Thread(target=run_cv_cell, args=(0, f"simul_chronovoltometrycycledummy0",  [[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1]))
        t0.start()
        t1 = threading.Thread(target=run_cv_cell, args=(8, f"simul_chronovoltometrycycledummy1",  [[0, -2, 2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1]))
        t1.start()
        t0.join()
        t1.join()
        """

        #run_geis_cell(8, "dummygeistest1")
        """ WORKS
        t0 = threading.Thread(target=run_geis_cell, args=(0, "dummy_geis_0"))
        t0.start()
        t1 = threading.Thread(target=run_geis_cell, args=(8, "dummy_geis_1"))
        t1.start()
        #join the threads started in the eval statements above
        t0.join()
        t1.join()
        """
        
        # t0 = threading.Thread(target=run_cp_cell, args=(0, 1.5, 60))
        # t0.start()
        # t1 = threading.Thread(target=run_cp_cell, args=(8, 1.5, 60))
        # t1.start()
        # t0.join()
        # t1.join()


        #run_cv_cell(8, "simultest1",  [[0, 3, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1])
        
        #for i in range(0,3):

            #data0 = run_cv_cell(0, mux, f"dummycelltest0c{i}",  [[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1])
            

            #mux.set_dac(0, 0.5)
            #data1 = run_cv_cell(1, mux, f"dummycelltest1c{i}",  [[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1])
            # t1 = threading.Thread(target=run_cv_cell, args=(1, f"chronovoltometrycycledummy1c{i}",  [[0, 2, -2, 0], [0.1, 0.1, 0.1], [1, 1, 1], 1, 0.1]))
            # t1.start()
            # t1.join()
            #mux.set_dac(1, 0.5)
        

        """
        pstat_list = []
        ps1 = tkp.Pstat("PSTAT")
        ps1.set_ctrl_mode(tkp.PSTATMODE)#for some reason unable to connect to pstats?
        print(ps1.label())
        for i in range(0,len(pstat_list_names)):
            pstat_list[i] = tkp.Pstat(pstat_list_names[i])
            print(pstat_list_names[i])
        """
        #values = [[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1]
        #cv = CV(values[0],values[1],values[2],values[3],values[4], tkp.PSTATMODE, imax = 10)
        #data = run_cv_cell("dummycelltest1", 0)
        #data2 = run_geis_cell("dummygeistest1", pstat_index=1)
        #print(data)
        #print(data)


        """
        df = pd.read_csv(run_file)
        run_standard = standard is not None
        if run_standard:
            # perform checks on disp rack and ensure vial has been added. 
            name = standard.get("name", "standard")
            try:
                pos = standard.get("pos")
            except:
                raise Exception("Need to provide a pos for standard!")
            
            tup = self.disp_rack.get_vial_by_pos(pos)
            if tup is None:
                raise Exception("Add standard vial to disp_rack.csv first!")

            if tup[0] != name:
                raise Exception(f"Make sure vial name at {pos} on disp_rack.csv is the same \
                                as what you provide to run_test()")
            
            #  add row before and after run file
            
            name = name + "_" + formatted_date
            row = [name, pos, standard.get("electrode_used"),True, "250000 1 0.00001", True, "2 -2 0.020", False, False]
            new_row = pd.DataFrame([row], columns=df.columns)
            df = pd.concat([new_row, df, new_row], ignore_index=True)



        # pass point1, pooint2, rate to run_cv_output 
        point1, point2, rate = [float(i) for i in test.CV_Conditions.split()]

        self.set_output(6, True)
        self.set_output(7, True)
        self.set_output(8, True)
        for j in range(3):
            self.move_vial(rack_disp_official[target_idx], vial_carousel)
            self.draw_to_sensor(target_idx, second_sensor=True)
            ocv = RunOCV_lastV()
            run_cv_output(output_file_name=output_file_name + f"_cv{i}",
                    values=[[ocv, point1, point2, 0],
                            [rate, rate, rate],
                            [0.05, 0.05, 0.05],
                            1,
                            0.1],
                    electrode_used = electrode_used,
                    save_to_db_folder = save_to_db,
                    standard=row_is_standard)
        self.set_output(6, False)
        self.set_output(7, False)
        self.set_output(8, False)
        """

    def cell_test_cp(self, cells, channels, set_voltages):
        """
        Docstring for cell_test_24
        
        :param self: Description
        :param cells: takes in a list with the indices of cells to run tests on
        """
        channel = channels[0]
        volts = set_voltages[0]
        tkp.toolkitpy_init("open_circuit_voltage.py")
        
        mux = tkp.IMX("mux1")
        mux.open()
        mux.set_off_mode(channel, volts)
        #mux.close()
        mux.setDAC(channel, 1)
        run_cv_cell("test_cv", 0, channel)
        run_geis_cell("test_geis", 0, channel)
        cells_tested = []
        for cell in range(1,len(cells)):
            index = cells[cell]
            cells_tested.append(index)
            for c in range(0,len(cells_tested)):
                pass

        pass

    def dispense_powder_and_scale(self, protocol, dest_id, mass, container_index=0, collect=False, ret=True):
        """
        dispense powder into specified vial (dest_id)
        """
        #self.check_remove_pipette()

        #if collect:
        #    self.move_vial(rack_disp_official[dest_id], vial_carousel)
        #else:
            #assumes already holding vial
        #    self.goto_safe(vial_carousel)
        self.move_carousel(0,0)
        #self.uncap_vial_in_carousel()
        self.move_carousel(68, 74) # carousel moves 68 degrees, 77 mm down

        start = time.time()
        p2 = PowderShaker('C', network=self.network)
        p2.init(container_index)
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

    def run_demo_nov11(self):
        """
        Run a demo for the class which is visiting the lab on November 11th
        """
        dispense_vial_prepared = input("Put a vial half-full of H2O, with a special cap (green w/ hole in middle) in the A1 position of the dispense rack. Type 1 once completed:  ")
        source_vial_prepared = input("Put a vial full of H2O in the B4 position of the source rack. Type 1 once completed:  ")
        carousel_is_empty = input("Remove any vial currently in the vial clamp.  Type 1 once completed:  ")
        heat_rack_empty = input("Remove all vials from the heating rack. Type 1 once completed:  ")

        if dispense_vial_prepared == '1' and source_vial_prepared == '1' and carousel_is_empty == '1' and heat_rack_empty  == '1':
            print("All conditions are fulfilled. Starting the program now!")
            self.delay(2.5)
            
        
            


            demo_velocity = 23
            #make sure that sourcerack(9) is full of water
            #make sure that disp_rack(0) is an empty vial
            #Print out any pre-reqs for running the program at the beginning, i.e. "Make sure that there are empty vials in positions 1, 2, and 3"        
            self.check_remove_pipette()
            self.open_clamp()
            self.open_gripper()
            self.goto_safe(safe_zone)
            self.goto_safe(rack_disp_official[0], vel=demo_velocity)
            self.close_gripper()
            self.delay(1)
            self.goto_safe(vial_carousel, vel=demo_velocity)
            
            self.close_clamp()
            self.delay(0.25)
            self.open_gripper()

            self.dispense_vol(0, 9, 1, ret=False, speed=12)

            #self.move_carousel(33,80)
            self.close_clamp()
            self.pump_n_times([33,80], 5)
            self.move_carousel(0,0)
            self.open_clamp()
            self.goto_safe(vial_carousel, vel=demo_velocity)
            self.close_gripper()
            self.delay(1)
            self.goto_safe(safe_zone, vel=demo_velocity)
            # self.spin_axis(0, 5000)
            self.goto_safe(heatplate_official2[0], vel=demo_velocity)
            self.open_gripper()
            self.spin_axis(6, 7000)
            self.delay(1)
            self.goto_safe(safe_zone, vel = demo_velocity)
            self.delay(10)
            self.spin_axis(0, 0)
            self.spin_axis(6, 0)
            self.spin_axis(7, 0)
            self.goto_safe(heatplate_official2[0], vel=demo_velocity)
            self.close_gripper()
            self.delay(0.75)
            self.goto_safe(rack_disp_official[0], vel = demo_velocity)
            self.open_gripper()
            self.delay(0.66)
            self.goto_safe(safe_zone, vel = demo_velocity)

            #t8.set_temp(0, 50)
            #self.t8.set_temp(1, 40)
            
            #self.goto_safe(safe_zone, vel=demo_velocity)


            """
            self.uncap()
            self.goto_safe(cap_holder_1_approach)
            self.cap(revs=3, torque_thresh=400)
            self.delay(0.66)
            
            self.goto_safe(rack_source_official_approach[9])
            self.close_gripper()
            self.delay(0.75)
            self.uncap()
            self.goto_safe(cap_holder_2_approach)
            self.cap(revs=3, torque_thresh=400)
            self.delay(0.66)
            self.open_gripper()
            self.get_pipette()
            """
            #self.aspirate_ml(3, 4)
            #self.dispense_vol(0, 9, 3)
        else:
            print("Not all conditions are fulfilled. Please check that all of the vials are in the right place, then type '1' for each of the conditions")
        pass


    def screw_setup(self, screw=0):
            if screw == 0:
                self.goto_safe(microplate_screwgrab_r)
                self.close_gripper()
                self.delay(0.5)
                self.goto_safe(e_cell_screw_r_approach)
                self.goto(e_cell_screw_r, vel = 1)
            else:
                self.goto_safe(microplate_screwgrab_l)
                self.close_gripper()
                self.delay(0.5)
                self.goto_safe(e_cell_screw_l_approach)
                self.goto(e_cell_screw_l, vel = 1)

    def screw_with_thresh_only(self, threshold, num_tries = 1):
        """
        Docstring for screw_with_thresh_only
        
        :param self: Description
        :param threshold: threshold, in mA. Usually ~1000 is good for screwing until any resistance is felt, below 750 it usually ends immediately
        :param num_tries: number of "RuntimeError: Sequence: CAPPING FAULT: Torque threshold not reached" errors we should go through. 
        Corresponds to like 2 rotations each. If you want you could probably just set this number to like 100 or something and it will skip through everything after you reach torque threshold
        """
        for i in range(0, num_tries):
            try:
                self.cap(pitch=2, revs=0, torque_thresh=threshold, vel=2500)
            except:
                pass
            finally:
                pass

    def transfer_board_to(self, position):
        """
        Docstring for transfer_board_to
        
        :param self: Description
        :param position: the position you'd like to transfer to. 1 = on the test stand (position closer to the right side), 0 = in the holding stand
        """
        #position 0 = off of the testing stand, pos 1 = on the testing stand
        #in the future perhaps store the position somewhere and choose which procedure to do based on that, but for now it's ok to manually define it
        self.open_gripper()
        if position == 0: #transfer to holding stand
            self.goto_safe(microplate_test_approach) #begin at test stand approach
            self.goto(microplate_test) 
            self.close_gripper()
            self.delay(1)
            self.goto(microplate_test_approach)
            self.goto(microplate_holder_approach)
            self.goto(microplate_holder, vel=1)
        else: #transfer to test stand
            self.goto_safe(microplate_holder_approach) #begin at holding stand approach
            self.goto(microplate_holder) 
            self.close_gripper()
            self.delay(1)
            self.goto(microplate_holder_approach)
            self.goto(microplate_test_approach)
            self.goto(microplate_test, vel=1)
            self.delay(1)
            #once board is transfered, screw it in!
            self.open_gripper()
            self.delay(1)
            self.screw_setup(0)#right side
            self.screw_with_thresh_only(1200, 8)
            self.open_gripper()
            self.goto_safe(safe_zone)
            self.screw_setup(1)#left side
            self.screw_with_thresh_only(1300, 8)
    

    def pump_n_times(self, carousel_position, n_pumps):
        self.move_carousel(carousel_position[0],carousel_position[1])
        for i in range(1, n_pumps):
            self.pump_helper(length=2500,v_in=10,v_out=5)#0.8 mL roughly
            self.delay(1)
    
    def goto_microplate(self, position):
        self.goto_safe([position[0], position[1]-250, position[2]-200, position[3]-150])



    def dispense_vol(self, dest_id, source_id, target_vol, collect=False, ret=True, speed = 8):
        """
        Dispense {target_vol} ml from vial with id {source_id} into vial with id {dest_id}
        Destination vials are from rack_dispense_official while source_vials are from
        rack_pipette_aspirate respectively (see Locators)
        """
        self.check_remove_pipette()
        self.goto_safe(rack_source_official[source_id], vel=speed)
        cap_holder_id = self.move_cap_to_holder()

        if collect:
            self.move_vial(rack_disp_official[dest_id], vial_carousel)
        else:
            self.goto_safe(vial_carousel, vel=speed)

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
            self.goto_safe(rack[source_id], vel=speed)
            self.aspirate_ml(3, amount)
            self.delay(3)
            self.goto_safe(carousel_dispense, vel=speed)
            self.move_pump(3, 0)
            self.delay(3)
            remaining -= amount
            self.source_rack.set_vial_by_pos(pos, curr_vol - amount)
        
        self.set_pump_speed(3, 15)
        dispensed = self.read_steady_scale()
        self.goto_safe(safe_zone, vel=speed)
        self.remove_pipette()

        if ret:
            self.cap_and_return_vial_to_rack(dest_id)
        else:
            self.close_clamp()
            self.goto_safe(vial_carousel_approach, vel=speed)
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
        1250 = 0.4 ml
        """
        #can use reservoir
        if self.res1_vol > self.vol_purge or self.res2_vol > self.vol_purge:
            if self.res1_vol > self.vol_purge:
                self.move_carousel(91, 85)
                self.res1_vol -= self.vol_purge
            # use second reservoir
            else:       
                self.move_carousel(137,85)
                self.res2_vol -= self.vol_purge

            for _ in range(n_pumps):
                self.pump_helper(length=length, v_in=speed, v_out=5)
            
            self.move_carousel(0, 0)

            for _ in range(6):
                self.pump_helper(length=length, v_in=15, v_out=5)
        # elif (self.res1_vol + self.res2_vol) >= self.vol_purge:
        #     remaining = self.vol_purge

        #     # draw from res1 first
        #     # 1250 = 0.4 ml
        #     self.move_carousel(91, 85)
        #     n_pumps_res1 = math.ceil( self.res1_vol / ((3000/1250) * 0.4) )

        #     for _ in range(n_pumps_res1):
        #         self.pump_helper(length=length, v_in=speed, v_out=5)

        #     self.res1_vol = 0
        #     remaining -= self.res1_vol

        #     # draw from res2 now
        #     self.move_carousel(137,85)
    
        #use water vials
        else:
            if self.water_start + 3 <= self.water_end + 1:
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
            else:
                raise CriticalRuntimeError("Error: No more water left to purge! Check configs for")

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

    def run_ce(self, source, target, target_vol):
        """
        Run CE

        (G_insert_CE_Stuff_here)

        source - position of source vial on disp_rack
        target - ID of target slot on microplate
        target_vol - volume to draw
        """

        #move vial to the carousel and uncap it
        self.move_carousel(0,0)
        self.move_vial(rack_disp_official[source], vial_carousel)
        self.uncap_vial_in_carousel()
        self.get_pipette()
        self.zero_scale()

        # draw from the vial in the carousel and dispense it at the microplate
        self.goto_safe(carousel_aspirate)
        self.aspirate_ml(target_vol)
        self.goto_safe(microplate_official[target])
        self.dispense_ml(target_vol)

        # remove pipette and cap and return vial
        self.remove_pipette()
        self.cap_and_return_vial_to_rack(source)

        #do whatever you want...

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

    def add_date_times_to_files(self):
        folder = Path("C:/AttomRobotFiles/Software/BatteryRobot/MainProject/src/main/res/cv")
        for file in folder.iterdir():
            if file.is_file():
                #print(file.name) # or file.absolute()
                s = file.stat().st_ctime
                readable_time = dt.fromtimestamp(s)
                r = random.randrange(0,100)
                if r == 0:
                    print(f"{r}, {file.name} created on {readable_time}")
                #creation_time = os.path.getctime(path)
                # Convert to readable datetime object
                #dt_object = datetime.datetime.fromtimestamp(creation_time)
                #print("File created on:", dt_object)


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

    def goto_notsosafe(self, position, vel=10):
        """
        Goto position without any safety checks. Use with caution.
        """
        current = self.get_robot_positions()
        self.move_z(current[3] + 100, vel=vel)
        self.goto([position[0], position[1], position[2], position[3] + 100], vel=vel)
        new = self.get_robot_positions()
        self.move_z(new[3] - 100, vel=vel)

    def move_cap_to_holder_rack_src(self, source_id, rack=rack_source_official):
        """
        Helper function to move cap to a free cap holder.
        Assumes gripper is at target vial's cap's location
        """
        self.goto_safe(rack[source_id])
        self.close_gripper()
        self.delay(.5)
        self.uncap(pitch = 1.35, revs=7)

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

        self.cap(revs=4, torque_thresh=400)
        self.open_gripper()
        self.delay(.5)
        return cap_holder_id

    def move_cap_to_holder(self):
        """
        Helper function to move cap to a free cap holder.
        Assumes gripper is at target vial's cap's location
        """
        self.close_gripper()
        self.delay(.5)
        self.uncap(pitch = 1.35, revs=7)

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

        self.cap(revs=4, torque_thresh=400)
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
        self.uncap(pitch = 1.35, revs=7)
        self.goto_safe(rack_source_official_approach[source_id])
        self.cap(revs=4, torque_thresh=400)
        self.open_gripper()
        # self.goto_safe(safe_zone)

    def rack_source_official_test(self, source_id = [0, 1, 2, 3, 4]):
        for i in source_id:
            self.move_cap_to_holder_rack_src(i)
            self.move_cap_from_holder(i, 1)
            self.delay(0.5)


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

    def initialize_deck(self, disp_rack_path, source_rack_path, heat_rack_path, heat_rack2_path):
        """
        Initialize deck by mapping rack contents
        """
        try:
            self.disp_rack = DispRack(disp_rack_path)
            self.source_rack = SourceRack(source_rack_path)
            self.heat_rack = HeatRack(heat_rack_path)
            self.heat_rack = HeatRack(heat_rack2_path)
        except InitializationError as e:
            print(e)
            print("Fix the rack csvs and try again.")