#CCD class creation
from enumerations import *
from Discharge import *
from Charge import *
from PwrGalvEIS import *
import ctypes
import os
import pandas as pd
import loop
from inspect import currentframe, getframeinfo
class ccd_set(loop):
    def __init__(self):
        self.dictionary = {'base_folder_name' : 'CCD', 'capacity' : 1, 'save_raw_data' : False, 'working' : True, 'expected_max_v' : 4.25, 'cell_type' : 'Full', 'IR': False, 'number_of_cycles' : 1000, 'first_step' : 'Charge', 'loop_end_1': loop_end.LOOP_END_DISCHARGETIMEUNDER, 'loop_end_1_val' : [0,0,3600], 'loop_end_2': loop_end.NoEnd, 'loop_end_2_val' : [0,0,0], 'eis_spectrum' : 'None', 'cable_check' : False, 'max_time' : 14400, 'sample_period' : 5  }
        self.experiment_list = []
        self.df = pd.DataFrame(columns = ['Pt', 'Time', 'Type', 'Cycle', 'Charge', 'Duration', 'Vstart', 'Vend']) #I have no clue how they average overloads. Is it just any of them that ever occured during that experiment?
    def dictionary_set(self, **kwargs):
        if 'base_folder_name' in kwargs.keys():
            if type(kwargs.get('base_folder_name')) == str:
                self.dictionary.update({'base_folder_name': kwargs.get('base_folder_name')})
                kwargs.pop('base_folder_name')
            else:
                print("The base_folder_name that you put in is not valid and the previous base_folder_name {} is being used".format(self.base_folder_name))
        if 'capacity' in kwargs.keys():
            if type(kwargs.get('capacity')) == (int,float):
                self.dictionary.update({'capacity':kwargs.get('capacity')})
                kwargs.pop('capacity')
            else:
                print("The capacity that you put in is not valid and the previous capacity {} is being used".format(self.capacity))
        if'save_raw_data' in kwargs.keys():
            if type(kwargs.get('save_raw_data')) == bool:
                self.dictionary.update({'save_raw_data': kwargs.get('save_raw_data')})
                kwargs.pop('save_raw_data')
            else:
                print("The save_raw_data that you put in is not valid and the previous save_raw_data {} is being used".format(self.save_raw_data))
        if 'working' in kwargs.keys():
            if type(kwargs.get('working')) == bool:
                self.dictionary.update({'working': kwargs.get('working')})
                kwargs.pop('working')
            else:
                print("The working that you put in is not valid and the previous working {} is being used".format(self.working))
        if 'expected_max_v' in kwargs.keys():
            if type(kwargs.get('expected_max_v')) == (int,float):
                self.dictionary.update({'expected_max_v':kwargs.get('expected_max_v')})
                kwargs.pop('expected_max_v')
            else:
                print("The expected_max_v that you put in is not valid and the previous expected_max_v {} is being used".format(self.expected_max_v))
        if 'cell_type' in kwargs.keys():
            if type(kwargs.get('cell_type')) == str:
                self.dictionary.update({'cell_type':kwargs.get('cell_type')})
                kwargs.pop('cell_type')
            else:
                print("The cell_type that you put in is not valid and the previous cell_type {} is being used".format(self.cell_type))
        if 'IR' in kwargs.keys():
            if type(kwargs.get('IR')) == bool:
                self.dictionary.update({'IR': kwargs.get('IR')})
                kwargs.pop('IR')
            else:
                print("The IR that you put in is not valid and the previous IR {} is being used".format(self.IR))
        if 'number_of_cycles' in kwargs.keys():
            if type(kwargs.get('number_of_cycles')) == int:
                self.dictionary.update({'number_of_cycles':kwargs.get('number_of_cycles')})
                kwargs.pop('number_of_cycles')
            else:
                print("The number_of_cycles that you put in is not valid and the previous number_of_cycles {} is being used".format(self.number_of_cycles))
        if 'first_step' in kwargs.keys():
            if type(kwargs.get('first_step')) == str:
                self.dictionary.update({'first_step':kwargs.get('first_step')})
                kwargs.pop('first_step')
            else:
                print("The first_step that you put in is not valid and the previous first_step {} is being used".format(self.first_step))
        if 'loop_end_1' in kwargs.keys():
            if isinstance(kwargs.get('loop_end_1'), loop_end):
                self.dictionary.update({'loop_end_1':kwargs.get('loop_end_1')})
                kwargs.pop('loop_end_1')
            else:
                print("The loop_end_1 that you put in is not valid and the previous loop_end_1 {} is being used".format(self.loop_end_1))
        if 'loop_end_1_val' in kwargs.keys():
            if type(kwargs.get('loop_end_1_val')) == (int,float):
                self.dictionary.update({'loop_end_1_val':kwargs.get('loop_end_1_val')})
                kwargs.pop('loop_end_1_val')
            else:
                print("The loop_end_1_val that you put in is not valid and the previous loop_end_1_val {} is being used".format(self.loop_end_1_val))
        if 'loop_end_2' in kwargs.keys():
            if isinstance(kwargs.get('loop_end_2'), loop_end):
                self.dictionary.update({'loop_end_2':kwargs.get('loop_end_2')})
                kwargs.pop('loop_end_2')
            else:
                print("The loop_end_2 that you put in is not valid and the previous loop_end_2 {} is being used".format(self.loop_end_2))
        if 'loop_end_2_val' in kwargs.keys():
            if type(kwargs.get('loop_end_2_val')) == (int,float):
                self.dictionary.update({'loop_end_2_val':kwargs.get('loop_end_2_val')})
                kwargs.pop('loop_end_2_val')
            else:
                print("The loop_end_2_val that you put in is not valid and the previous loop_end_2_val {} is being used".format(self.loop_end_2_val))
        if 'eis_spectrum' in kwargs.keys():
            if type(kwargs.get('eis_spectrum')) == str:
                self.dictionary.update({'eis_spectrum':kwargs.get('eis_spectrum')})
                kwargs.pop('eis_spectrum')
            else:
                print("The eis_spectrum that you put in is not valid and the previous eis_spectrum {} is being used".format(self.eis_spectrum))
        print("These are the parameters that were deemed invalid")
        print(kwargs)

    def print_dictionary(self):
        print(self.dictionary)
    def discharge_values(self, discharge):
        if isinstance(discharge, discharge_set):
            self.discharge_dictionary = discharge.dictionary
        else:
            print("The object entered in was not a discharge item")
    def charge_values(self, charge):
        if isinstance(charge, charge_set):
            self.charge_dictionary = charge.dictionary
        else: 
            print("The object entered in was not a charge item")
    def geis_values(self, geis):
        if isinstance(geis, pwr_galv_eis_set):
            self.geis_dictionary = geis.dictionary
        else:
            print("The object entered in was not a geis item")
    def save_parameters(self, parameter_name, path):
        "Overloaded save_parameters that has the file directory"
        if type(parameter_name) != str:
            print("Please input a string as a file name")
            return
        if parameter_name == "Placeholder" :
            parameter_name = self.dictionary.get('file_name') + '_parmaters.pickle'
        if not parameter_name.endswith('.pickle'):
            parameter_name = parameter_name + '.pickle'
        with open(path+ '\\' + parameter_name,  'wb') as handle:
            pickle.dump([self.dictionary, self.charge_dictionary, self.discharge_dictionary, self.pwr_galv_eis_dictionary], handle, protocol = pickle.HIGHEST_PROTOCOL)
    def load_parameters(self, path):
            """loads a dictionary from a pickle file and sets the instance variables to the loaded parameters """
            if not path.endswith('.pickle'):
                  path = path + '.pickle'
            with open(path, 'rb') as handle:
                  unserialized_data = pickle.load(handle)
            self.dictionary = unserialized_data[0]
            self.charge_dictionary = unserialized_data[1]
            self.discharge_dictionary = unserialized_data[2]
            self.pwr_galv_eis_dictionary = unserialized_data[3]
    def display_parameters(self):
        print("Here are the loop parameters")
        print(self.dictionary)
        if self.charge_dictionary != None:
            print("Here are the charge parameters")
            print(self.charge_dictionary)
        if self.discharge_dictionary != None:
            print("Here are the discharge parameters")
            print(self.discharge_dictionary)   
        if self.pwr_galv_eis_dictionary!= None:
            print("Here are the galvanostatic EIS parameters")
            print(self.pwr_galv_eis_dictionary)
        print("\n")
    def get_base_folder_name(self):
        return self.dictionary.get('base_folder_name')
    def set_base_folder_name(self, base_folder_name):
        self.dictionary.update({'base_folder_name':base_folder_name})
    def get_capacity(self):
        return self.dictionary.get('capacity')
    def set_capacity(self, capacity):
        self.dictionary.update({'capacity':capacity})
    def get_save_raw_data(self):
        return self.dictionary.get('save_raw_data')
    def set_save_raw_data(self, save_raw_data):
        self.dictionary.update({'save_raw_data':save_raw_data})
    def get_working(self):
        return self.dictionary.get('working')
    def set_working(self, working):
        self.dictionary.update({'working':working})
    def get_expected_max_v(self):
        return self.dictionary.get('expected_max_v')
    def set_expected_max_v(self, expected_max_v):
        self.dictionary.update({'expected_max_v':expected_max_v})
    def get_cell_type(self):
        return self.dictionary.get('cell_type')
    def set_cell_type(self, cell_type):
        self.dictionary.update({'cell_type':cell_type})
    def get_IR(self):
        return self.dictionary.get('IR')
    def set_IR(self, IR):
        self.dictionary.update({'IR':IR})
    def get_number_of_cycles(self):
        return self.dictionary.get('number_of_cycles')
    def set_number_of_cycles(self, number_of_cycles):
        self.dictionary.update({'number_of_cycles':number_of_cycles})
    def get_first_step(self):
        return self.dictionary.get('first_step')
    def set_first_step(self, first_step):
        self.dictionary.update({'first_step':first_step})
    def get_loop_end_1(self):
        return self.dictionary.get('loop_end_1')
    def set_loop_end_1(self, loop_end_1):
        self.dictionary.update({'loop_end_1':loop_end_1})
    def get_loop_end_1_val(self):
        return self.dictionary.get('loop_end_1_val')
    def set_loop_end_1_val(self, loop_end_1_val):
        self.dictionary.update({'loop_end_1_val':loop_end_1_val})
    def get_loop_end_2(self):
        return self.dictionary.get('loop_end_2')
    def set_loop_end_2(self, loop_end_2):
        self.dictionary.update({'loop_end_2':loop_end_2})
    def check_charge(self):
        dictionary = self.charge_dictionary
        charge_value = dictionary.get('charge_value')
        capacity = dictionary.get('capacity')
        mode = dictionary.get('mode')
        time_matrix = dictionary.get('time_matrix')
        sample_period = dictionary.get('sample_period')
        stop_at1 = dictionary.get('stop_at1')
        stop_at1_val = dictionary.get('stop_at1_val')
        stop_at2 = dictionary.get('stop_at2')
        stop_at2_val = dictionary.get('stop_at2_val')
        voltage_finish = dictionary.get('voltage_finish')     
        expected_max_v = dictionary.get('expected_max_v')
        voltage_finish_time = dictionary.get('voltage_finish_time')
        voltage_finish_value = dictionary.get('voltage_finish_value')
        IR = dictionary.get('IR')
        working = dictionary.get('working')
        file_name = dictionary.get('file_name')

        #Do not change these
        #-------------------------------
        SAMPLINGMODE_NR = 1
        PWR800_DEFAULT_PERTURBATION_RATE = 0.01
        PWR800_DEFAULT_PERTURBATION_WIDTH = 0.003333
        PWR800_DEFAULT_TIMER_RESOLUTION = 0.0016666666
        PWR800_DEFAULT_MAXIMUM_STEP = 0.05
        PWR800_DEFAULT_MINUMUM_DIFFERENCE = 0.15
        PWR800_DEFAULT_CV_CP_GAIN = 0.05
        PWR800_DEFAULT_CR_GAIN = 1.0
        PWR800_DEFAULT_TI = 5.0
        min_dif = 0.15
        max_step = 0.05
        default_perturbation_rate = 0.01
        default_perturbation_width = 0.003333
        timer_res = 0.0016666666
        default_ti = 5.0
        Gain = PWR800_DEFAULT_CV_CP_GAIN
        #------------------------------------
        step_one_time = (time_matrix)
        curve = PWRWrapper(pstat,10000)
        if(voltage_finish == True):
            if ((stop_at1 != stop_ats.PWR_STOP_AVMAXSTOP) and (stop_at2 != stop_ats.PWR_STOP_AVMAXSTOP)
            and (stop_at1 != stop_ats.PWR_STOP_VMAXSTOP) and (stop_at2 != stop_ats.PWR_STOP_VMAXSTOP)
            and (stop_at1 != stop_ats.PWR_STOP_AVMINSTOP) and (stop_at2 != stop_ats.PWR_STOP_AVMINSTOP)):
                frame = getframeinfo(currentframe())
                errormessage = "Missing Stop At. \n At least one stop at must be voltage > limit if voltage finish is to be used \n\n You can find the code for this error around line: {}".format(frame.lineno)
                result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
                if (result == 1):
                    return
        if (((stop_at1 == stop_ats.PWR_STOP_VMAXSTOP ) or (stop_at2 == stop_ats.PWR_STOP_VMAXSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMINSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMINSTOP)) 
            and (working == False)):
            frame = getframeinfo(currentframe())
            errormessage = "Invalid Stop At. \n Working negative requires |Voltage| limit test.  \n\n You can find the code for this error around line: {}".format(frame.lineno)
            result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
            if (result == 1):
                return

    def input_experiments(self, pwr_experiment):
         pwr_experiment.check()
         if (isinstance(pwr_experiment, charge_set, discharge_set)):
             pwr_experiment.leave_switch_on = True
         else:
             pwr_experiment.leave_switch_on = False 
         self.experiment_list.append(pwr_experiment)
    def get_experiment_list(self):
        return self.experiment_list
    

    def CCD_prep(self):
         folder_name = self.dictionary.get('base_folder_name')
         # I am not going to delete the folder if it already exists an error will just be returned 
         if(os.path.exists(folder_name)):
              frame = getframeinfo(currentframe())
              errormessage = "Folder {} already exists".format(folder_name)
              result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
              del pstat
              return
    def create_folder(self, folder_name):
        if not os.path.exists():
            os.makedirs(folder_name)
        else:
            errormessage = "Folder {} already exists".format(folder_name)
            result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30)
        

         
    def run(self):
        start_time = time.time()
        cycle = 1
        pt = 1 #This will track the number of experiments
        #j is the inner loop counter to run each experiment
        #i is the numer of cycles to run
        last = None
        next_start = None
        inner_timestart = None
        end_inner_timestart = None
        while i <= self.get_number_of_cycles():
            if self.exit_loop:
                break
            for j in self.experiment_list:
                inner_timestart = time.time()
                data = j.run()
                end_inner_timestart = time.time()
                next_start = int(time.time() - start_time)
                if j.experimetnal_type == "charge" or i.experimetnal_type == "discharge":
                    capacity = np.mean(data['im']) * (data['time'][-1]- data['time'][0])
                    self.df.loc[len(self.df.index)] = [pt,next_start, i.experimental_type,capacity,end_inner_timestart- inner_timestart, data['vf'][0],data['vf'][-1]]
                pt = pt + 1
            i = i + 1








         
             
         
         
         #Usually all the stops ats would be here for both charge and discharge modes however my goal would be to have this simply loop charge and discharge objects as its primary function
         #implmentation of raw data save comes later. We just have to get this to work. 

        
        #We have to determine the steps inside. As of right now all we have is charge discharge and Galv EIS 
         

        
    
        

