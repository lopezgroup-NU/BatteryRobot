from pynput import keyboard
import tkinter
import sys
# sys.path.append(r'C:\Users\ablack.GAMRY\Documents\Jupyter\Supporting\Release')
import toolkitpy as tkp
#from toolkitcommon import *
#from toolkitcurves import *
# import UniversalGraph as Graph
from enum import Enum
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
import pandas as pd                      #Used for presenting data in tables
import matplotlib.pyplot as plt          #Used to plot data
from scipy import stats                  #Used for linear regression
import csv                               #Used to export data as csv files
import traceback                         #Used for error catching
import math
import pickle
import PWR800
import ctypes
import os
from pathlib import Path
from inspect import currentframe, getframeinfo
from matplotlib.widgets import Button
# from enumerations import stop_ats, pwrmodes,cell_types
# from experiment import experiment

#matplolib notebook activates QT GUI for dynamic plots
from mpl_point_clicker import clicker  #Used for plotting

class charge_set(experiment):
      counter = 1
      type = 0
      experimental_type = 'charge'
      def __init__(self,pstat):
            self.dictionary = {'file_name' : 'PWRCHARGE.csv', 'capacity' : 1, 'IR' : False, 'cell_type' : cell_types.CELL_TYPE_HALF , 'working' : True, 'expected_max_v' : 4.25, 'mode' : pwrmodes.PWR_MODE_CURRENT_CHARGE, 'charge_value' : 1,
                                'time_matrix' : [4,0,0], 'sample_period' : 5, 'stop_at1' : stop_ats.PWR_STOP_VMAXSTOP, 'stop_at1_val' : 3, 'stop_at2' : stop_ats.NoStop, 'stop_at2_val' : 0, 'voltage_finish' : False, 'voltage_finish_time' : [0,0,3600],
                                 'voltage_finish_value' : .001 }
            if pstat.has('SaveBothHalfCells'):
                  self.aesbhc = True
            self.checked = False
            #self.iteration = self.iteration + 1
            self.cell_lead_check = False
            self.pstat = pstat
      def dictionary_set(self, **kwargs):
            """This allows you to pass in kew word arguements to set multiple parameters at once. The keywords are the names of the paramters themselves. 
            Any arguement that doesn't have the exact right name will not be added. This will try its best to display which ones were thrown out.
            It prints out the new dictionary that was created. And also updates the instance variables of the class"""
            self.dictionary =  dict()
            if 'file_name' in kwargs.keys():
                  if type(kwargs.get('file_name')) == str:
                        self.dictionary.update({'Filename': kwargs.get('file_name')})
                        kwargs.pop('file_name')
                  else:
                        print("The file_name that you put in is not valid and the previous file_name {} is being used".format(self.file_name))
            if 'capacity' in kwargs.keys():
                  if type(kwargs.get('capacity')) == float or type(kwargs.get('capacity')) == int:
                        self.dictionary.update({'capacity':kwargs.get('capacity')})
                        kwargs.pop('capacity')
                        self.checked  = False
                  else:
                        print("The capacity that you put in is not valid and the previous capacity {} is being used".format(self.capacity))
            if 'IR' in kwargs.keys():
                  if type(kwargs.get('IR')) == bool:
                        self.dictionary.update({'IR' : kwargs.get('IR')})
                        kwargs.pop('IR')
                        self.checked  = False
                  else: 
                        print("The IR setting that you put in is not valid and the IR value is still {}".format(self.IR))
            if 'CellType' in kwargs.keys():
                  if isinstance(kwargs.get('CellType'), cell_types):
                        self.dictionary.update({'CellType':kwargs.get('CellType')})
                        kwargs.pop('CellType')
                        self.checked  = False
                  else:
                        print("The Cell type that you put in is not valid it should be a cell_type enumeration and it you entered a(n) {} the previous value of {} will be used".format(type(kwargs.get('CellType')), self.CellType))
            if 'working' in kwargs.keys():
                  if type(kwargs.get('working')) == bool:
                        self.dictionary.update({'working' : kwargs.get('working')})
                        kwargs.pop('working')
                        self.checked  = False
                  else:
                        print("The working configuration that you placed is invalid it has to be a boolean and you entered a {} the previous value: {} will be used".format(type(kwargs.get('working')),self.working))
            if 'expected_max_v' in kwargs.keys():
                  if type(kwargs.get('expected_max_v')) == float or type(kwargs.get('expected_max_v')) == int: 
                        self.dictionary.update({'expected_max_v':kwargs.get('expected_max_v')})
                        kwargs.pop('expected_max_v')
                        self.checked  = False
                  else:
                        print("The expected max v that you entered was not valid. You entered a {} and max v is supposed to be a float or int the previous value: {} will be used".format(type(kwargs.get('expected_max_v')), self.expected_max_v))
            if 'mode' in kwargs.keys():
                  if type(kwargs.get('mode')) == pwrmodes:
                        self.dictionary.update({'mode': kwargs.get('mode')})
                        kwargs.pop('mode')
                        self.checked  = False
                  else:
                        print("The mode that you put in is invalid. It has to be an enumerator from pwrmodes. The previous value: {} will be used".format(self.mode))
            if 'charge_value' in kwargs.keys():
                  if type(kwargs.get('charge_value')) == float or type(kwargs.get('charge_value')) == int :
                        self.dictionary.update({'charge_value':kwargs.get('charge_value')})
                        kwargs.pop('charge_value')
                        self.checked  = False
                  else: 
                        print("The charge value that you entered is not valid it must be an int or a float. The previous value {} will be used".format(self.charge_value))      
            if 'time_matrix' in kwargs.keys():
                  if type(kwargs.get('time_matrix')) == list and len(kwargs.get('time_matrix')) == 3 and all(isinstance(x,(int,float)) for x in kwargs.get('time_matrix')):    
                        self.dictionary.update({'time_matrix' : kwargs.get('time_matrix')})
                        kwargs.pop('time_matrix')
                  else:
                        print("The time_matrix that you entered is invalid. This is expecting a 3 length matrix formated [hours, minutes, seconds]. The previous value {} will be used".format(self.time_matrix))
            if 'sample_period' in kwargs.keys():
                  if type(kwargs.get('sample_period')) == (float,int):
                        self.dictionary.update({'sample_period':kwargs.get('sample_period')})
                        kwargs.pop('sample_period')
                  else:
                        print("The sample period that you inputted is invalid this is expecting a float or int. The previous value of {} will be used".format(self.sample_period))
            if 'stop_at1' in kwargs.keys():
                  if isinstance(kwargs.get('stop_at1'),stop_ats):
                        self.dictionary.update({'stop_at1' : kwargs.get('stop_at1')})
                        kwargs.pop('stop_at1')
                        self.checked  = False
                  else:
                        print("The first stop at conidtion that you inputted is not a member of the stop_ats enumerations. The previous value of {} will be used".format(self.stop_at1))
            if 'stop_at1_val' in kwargs.keys():
                  if type(kwargs.get('stop_at1_val')) == (int,float):
                        self.dictionary.update({'stop_at1_val':kwargs.get('stop_at1_val')})
                        kwargs.pop('stop_at1_val')
                        self.checked  = False
                  else: 
                        print("The first stop at value is invalid. The value should be a float or an int. The previous value: {} will be used".format(self.stop_at1_val))
            if 'stop_at2' in kwargs.keys():
                  if isinstance(kwargs.get('stop_at2'),stop_ats):
                        self.dictionary.update({'stop_at2': kwargs.get('stop_at2')})
                        kwargs.pop('stop_at2')
                        self.checked  = False
                  else:
                        print("The second stop at condition that you entered is invalid. It should be a memeber of the stop_ats enumerations. The previous stop at of {} will be used".format(self.stop_at2))
            if 'self.stop_at2_val' in kwargs.keys():
                  if type(kwargs.get('stop_at2_val')) == (float,int):
                        self.dictionary.update({'stop_at2_val':kwargs.get('stop_at2_val')})
                        kwargs.pop('stop_at2_val')
                        self.checked  = False
                  else:
                        print("The second stop at value that you entered is not valid. This should be an int or float. The previous value of {} will be used".format(self.stop_at2_val))
            if 'voltage_finish' in kwargs.keys():
                  if type(kwargs.get('voltage_finish')) == bool:
                        self.dictionary.update({'voltage_finish' : kwargs.get('voltage_finish')})
                        kwargs.pop('voltage_finish')
                        self.checked  = False
                  else:
                        print("The voltage finish that was entered is invalid it should be a boolean. The previous value {} will be used".format(self.voltage_finish))
            if 'voltage_finish_time' in kwargs.keys():
                  if type(kwargs.get('voltage_finish_time')) == list and len(kwargs.get('voltage_finish_time')) == 3 and all(isinstance(x,(int,float)) for x in kwargs.get('voltage_finish_time')):
                        self.dictionary.update({'voltage_finish_time' : kwargs.get('voltage_finish_time')})
                        kwargs.pop('stop_at1')
                  else: 
                        print("The voltage finish time that you entered was invalid. It should be a list that of length 3. All of the members of the list should be a float or int. The previous value of {} is being used".format(self.voltage_finish_time))
            if 'self.voltage_finish_value' in kwargs.keys():
                  if type(kwargs.get('voltage_finish_value')) == (float,int):
                        self.dictionary.update({'self.voltage_finish_value':kwargs.get('self.voltage_finish_value')})
                        kwargs.pop('self.voltage_finish_value')
                  else:
                        print("The voltage finish current that you entered is invalid. It should be of type int or float. The previous value of {} will be used".format(self.set_voltage_finish_value))
            print("These are the parameters that were deemed invalid")
            self.checked = False
            print(kwargs)
      # def to_dictionary(self):
      #       """Updates the dictionary with the instance variables"""
      #       dictionary = dict()
      #       dictionary.update({'capacity' : self.capacity, 'IR' : self.IR, 'CellType' : self.CellType, 'working' : self.working, 'expected_max_v' : self.expected_max_v, 'mode' : self.mode,
      #                         'charge_value' : self.charge_value, 'time_matrix' : self.time_matrix, 'sample_period' : self.sample_period, 'stop_at1' : self.stop_at1 ,'stop_at1_val' : self.stop_at1_val,
      #                         'stop_at2' : self.stop_at2, 'stop_at2_val' : self.stop_at2_val, 'voltage_finish' : self.voltage_finish, 'voltage_finish_time' : self.voltage_finish_time, 'voltage_finish_value' : self.voltage_finish_value})
      #       self.dictionary = dictionary
      #       return self.dictionary

      # def update_variables(self):
      #       self.capacity = self.dictionary.get('capacity')
      #       self.IR = self.dictionary.get('IR')
      #       self.CellType = self.dictionary.get('CellType')
      #       self.working = self.dictionary.get("working")
      #       self.expected_max_v = self.dictionary.get("expected_max_v")
      #       self.mode = self.dictionary.get("mode")
      #       self.charge_value = self.dictionary.get("charge_value")
      #       self.time_matrix = self.dictionary.get("time_matrix")
      #       self.sample_period = self.dictionary.get("sample_period")
      #       self.stop_at1 = self.dictionary.get("stop_at1")
      #       self.stop_at1_val = self.dictionary.get("stop_at1_val")
      #       self.stop_at2 = self.dictionary.get('stop_at2')
      #       self.stop_at2_val = self.dictionary.get('stop_at2_val')
      #       self.voltage_finish = self.dictionary.get('voltage_finish')
      #       self.voltage_finish_time = self.dictionary.get('voltage_finish_time')
      #       self.voltage_finish_value = self.dictionary.get('voltage_finish_value')

  
      def get_capacity(self):
          return self.dictionary.get('capacity')
  
      def set_capacity(self, value: float):
          self.dictionary.update({'capacity' : value})
          self.checked = False
  
      def get_IR(self):
          return self.dictionary.get('IR')
  
      def set_IR(self, value : bool):
          self.dictionary.update({'IR' : value})
          self.checked = False
  
      def get_cell_type(self):
          return self.dictionary.get('cell_type')
  
      def set_cell_type(self, value:str):
          self.dictionary.update({'cell_type' : value})

  
      def get_working(self):
          return self.dictioanry.get('working')
  
      def set_working(self, value : bool):
          self.dictionary.update({'working' : value})
          self.checked = False
  
      def get_expected_max_v(self):
          return self.dictionary.get('expected_max_v')
  
      def set_expected_max_v(self, value : float):
          self.dictionary.update({'expected_max_v' : value})
          self.checked = False
  
      def get_mode(self):
          return self.dictionary.get('mode')
  
      def set_mode(self, value:pwrmodes):
          self.dictionary.update({'mode' : value})
          self.checked = False
  
      def get_charge_value(self):
          return self.dictionary.get('charge_value')
  
      def set_charge_value(self, value :float):
          self.dictionary.update({'charge_value': value})
          self.checked = False
  
      def get_time_matrix(self):
          return self.dictionary.get('time_matrix')
  
      def set_time_matrix(self, value:list):
            self.dictionary.update({'time_matrix' : value})
  
      def get_sample_period(self):
          return self.dictionary.get('sample_period')
  
      def set_sample_period(self, value:float):
          self.dictionary.update({'sample_period' : value})
  
      def get_stop_at1(self):
          return self.dictionary.get('stop_at1')
  
      def set_stop_at1(self, value:stop_ats):
          self.dictionary.update({'stop_at1' : value})
          self.checked = False
  
      def get_stop_at1_val(self):
          return self.dictionary.get('stop_at1_val')
  
      def set_stop_at1_val(self, value : float):
          self.dictionary.update({'stop_at1_val' : value})
          self.checked = False
  
      def get_stop_at2(self):
          return self.dictionary.get('stop_at2')
  
      def set_stop_at2(self, value:stop_ats):
          self.dictionary.update({'stop_at2' : value})
          self.checked = False
  
      def get_stop_at2_val(self):
          return self.dictionary.get('stop_at2_val')
  
      def set_stop_at2_val(self, value : float):
            self.dictionary.update({'set_stop_at2_val' : value})
            self.checked = False
  
      def get_voltage_finish(self):
          return  self.dictionary.get('voltage_finish')
  
      def set_voltage_finish(self, value : bool):
           self.dictionary.update({'voltage_finish' : value})
  
      def get_expected_max_v(self):
          return  self.dictionary.get('expected_max_v')

      def set_expected_max_v(self, value : float) :
           self.dictionary.update({'expected_max_v' : value})
           self.checked = False
  
      def get_voltage_finish_time(self):
          return self.dictionary.get('voltage_finish_time')
  
      def set_voltage_finish_time(self, value : list):
           self.dictionary.update({'voltage_finish_time' : value})
           self.checked = False
  
      def get_voltage_finish_value(self):
          return self.dictionary.get('voltage_finish_value')
  
      def set_voltage_finish_value(self, value:float):
            self.dictionary.update({'voltage_finish_value' : value}) 
      def run(self):
            """Runs the experiment requires a pstat input"""
            self.Charge()

      def time_conversion(array):
            conversion_mat = [3600, 60, 1]
            output_time = np.dot(array,conversion_mat)
            return output_time
      def mode_conversion(mode):
            if mode == pwrmodes.PWR_CURRENT_DISCHARGE:
                  mode = 0
            elif mode == pwrmodes.PWR_MODE_RESISTANCE:
                  mode = 1
            elif mode == pwrmodes.PWR_MODE_POWER:
                  mode == 2
            elif mode == pwrmodes.PWR_MODE_VOLTAGE:
                  mode = 3
            elif mode == pwrmodes.PWR_MODE_CURRENT_CHARGE:
                  mode = 4
            elif mode == pwrmodes.PWR_MODE_VOLTAGE_PSTATMODE:
                  mode = 5
            return mode

      def check(self):
            
            self.checked = True
            charge_value = self.dictionary.get('charge_value')
            capacity = self.dictionary.get('capacity')
            mode = self.dictionary.get('mode')
            time_matrix = self.dictionary.get('time_matrix')
            sample_period = self.dictionary.get('sample_period')
            stop_at1 = self.dictionary.get('stop_at1')
            stop_at1_val = self.dictionary.get('stop_at1_val')
            stop_at2 = self.dictionary.get('stop_at2')
            stop_at2_val = self.dictionary.get('stop_at2_val')
            voltage_finish = self.dictionary.get('voltage_finish')     
            expected_max_v = self.dictionary.get('expected_max_v')
            voltage_finish_time = self.dictionary.get('voltage_finish_time')
            voltage_finish_value = self.dictionary.get('voltage_finish_value')
            cell_type = self.dictionary.get('cell_type')
            IR = self.dictionary.get('IR')
            working = self.dictionary.get('working')
            file_name = self.dictionary.get('file_name')
            

            if(voltage_finish == True):
                  if ((stop_at1 != stop_ats.PWR_STOP_AVMAXSTOP) and (stop_at2 != stop_ats.PWR_STOP_AVMAXSTOP)
                  and (stop_at1 != stop_ats.PWR_STOP_VMAXSTOP) and (stop_at2 != stop_ats.PWR_STOP_VMAXSTOP)
                  and (stop_at1 != stop_ats.PWR_STOP_AVMINSTOP) and (stop_at2 != stop_ats.PWR_STOP_AVMINSTOP)):
                        frame = getframeinfo(currentframe())
                        errormessage = "Missing Stop At. \n At least one stop at must be voltage > limit if voltage finish is to be used \n\n You can find the code for this error around line: {}".format(frame.lineno)
                        result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
                        if (result == 1):
                              del self.pstat
                              return
            if (((stop_at1 == stop_ats.PWR_STOP_VMAXSTOP ) or (stop_at2 == stop_ats.PWR_STOP_VMAXSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMINSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMINSTOP)) 
                  and (working == False)):
                  frame = getframeinfo(currentframe())
                  errormessage = "Invalid Stop At. \n working negative requires |Voltage| limit test.  \n\n You can find the code for this error around line: {}".format(frame.lineno)
                  result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
                  if (result == 1):
                        del self.pstat
                        return
            PWR800.PWR800ConfigureAndConfirm(self.pstat, expected_max_v,working, cell_type,self.aesbhc, self.cell_lead_check) 
            
      def Charge (self):
            if self.checked == False:
                  self.check()
            charge_value = self.dictionary.get('charge_value')
            capacity = self.dictionary.get('capacity')
            mode = self.dictionary.get('mode')
            time_matrix = self.dictionary.get('time_matrix')
            sample_period = self.dictionary.get('sample_period')
            stop_at1 = self.dictionary.get('stop_at1')
            stop_at1_val = self.dictionary.get('stop_at1_val')
            stop_at2 = self.dictionary.get('stop_at2')
            stop_at2_val = self.dictionary.get('stop_at2_val')
            voltage_finish = self.dictionary.get('voltage_finish')     
            expected_max_v = self.dictionary.get('expected_max_v')
            voltage_finish_time = self.dictionary.get('voltage_finish_time')
            voltage_finish_value = self.dictionary.get('voltage_finish_value')
            IR = self.dictionary.get('IR')
            working = self.dictionary.get('working')
            file_name = self.dictionary.get('file_name')
            cell_type = self.dictionary.get('cell_type')
            if charge_set.counter > 1 : 
                  temp = Path(file_name)
                  file_name = "{0}_{2}{1}".format(temp.stem, temp.suffix, str(charge_set.counter))
            
            charge_set.counter += 1

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
            PWR800.PWR800ConfigureAndConfirm(self.pstat, expected_max_v,working, cell_type,self.aesbhc, self.cell_lead_check)
            PWR800.PWR800initializepstat(self.pstat,IR, self.dictionary.get('cell_type'),None)
            curve = PWRWrapper(self.pstat,10000)
            if(voltage_finish == True):
                  if ((stop_at1 != stop_ats.PWR_STOP_AVMAXSTOP) and (stop_at2 != stop_ats.PWR_STOP_AVMAXSTOP)
                  and (stop_at1 != stop_ats.PWR_STOP_VMAXSTOP) and (stop_at2 != stop_ats.PWR_STOP_VMAXSTOP)
                  and (stop_at1 != stop_ats.PWR_STOP_AVMINSTOP) and (stop_at2 != stop_ats.PWR_STOP_AVMINSTOP)):
                        frame = getframeinfo(currentframe())
                        errormessage = "Missing Stop At. \n At least one stop at must be voltage > limit if voltage finish is to be used \n\n You can find the code for this error around line: {}".format(frame.lineno)
                        result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
                        if (result == 1):
                              del self.pstat
                              return
            if (((stop_at1 == stop_ats.PWR_STOP_VMAXSTOP ) or (stop_at2 == stop_ats.PWR_STOP_VMAXSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMINSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMINSTOP)) 
                  and (working == False)):
                  frame = getframeinfo(currentframe())
                  errormessage = "Invalid Stop At. \n working negative requires |Voltage| limit test.  \n\n You can find the code for this error around line: {}".format(frame.lineno)
                  result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
                  if (result == 1):
                        del self.pstat
                        return
            if(voltage_finish == True):
                  if((stop_at1 == stop_ats.PWR_STOP_AVMINSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMAXSTOP) or (stop_at1 == stop_ats.PWR_STOP_VMINSTOP)):
                        stop_limit = stop_at1_val
                  else: 
                        stop_limit = stop_at2_val
                        second_mode = pwrmodes.PWR_VOLTAGE
                        second_time = voltage_finish_time
                        second_limit = charge_value
                        secondValue = stop_limit
                        curve.set_aimin(voltage_finish_value) ##This is going to have to change when I am on site
            else:
                  second_value = charge_value
                  second_mode = pwrmodes.PWR_MODE_CURRENT_CHARGE
                  second_limit = 0.0
                  second_time = [0,0,0]
            if stop_at1 == stop_ats.PWR_STOP_VMAXSTOP:
                        curve.set_stop_v_max(True, stop_at1_val)
            elif stop_at1 == stop_ats.PWR_STOP_AVMINSTOP:
                        curve.set_stop_av_min(True, stop_at1_val)
            elif stop_at1 == stop_ats.PWR_STOP_AVMAXSTOP:
                        curve.set_stop_av_max(True, stop_at1_val)
            elif stop_at1 == stop_ats.PWR_STOP_VMINSTOP:
                        stop_at1_val == curve.set_stop_v_min(True, stop_at1_val)
                  # Further implmentation for other stop at values
            if stop_at2 == stop_ats.PWR_STOP_VMAXSTOP:
                        curve.set_stop_v_max(True, stop_at2_val)
            elif stop_at2 == stop_ats.PWR_STOP_AVMINSTOP:
                        curve.set_stop_av_min(True, stop_at2_val)
            elif stop_at2 == stop_ats.PWR_STOP_VMINSTOP:
                        curve.set_stop_v_min(True, stop_at2_val)
            elif stop_at2 == stop_ats.PWR_STOP_AVMAXSTOP:
                        stop_at2_val == curve.set_stop_av_max(True, stop_at2_val)
            second_mode = charge_set.mode_conversion(second_mode)
            mode = charge_set.mode_conversion(mode)
            mode_matrix = [mode, second_mode]
            charge_values = [charge_value, second_value]
            time1 = charge_set.time_conversion(step_one_time)
            time2 = charge_set.time_conversion(second_time)
            time_matrix = [time1, time2]
            limit_mat = [0, second_limit]
            signal = self.pstat.signal_pwr_step_new(charge_values, limit_mat, Gain, default_ti, min_dif, max_step, time_matrix, sample_period, default_perturbation_rate, default_perturbation_width, timer_res, mode_matrix, working)
            self.pstat.set_ctrl_mode(GSTATMODE)
            self.pstat.set_signal_pwr_step(signal)
            self.pstat.init_signal()
            self.pstat.set_cell(CELL_ON)
            def on_press(key): #This is for debugging it allows for You to stop the curve while running with a button
                  if key == keyboard.Key.esc:
                        curve.stop()
                        print("Stop!")
            listener = keyboard.Listener(on_press = on_press)
            curve.run(True)
            fig = plt.figure()
            ax = fig.gca()
            listener = keyboard.Listener(on_press = on_press)
            listener.start()
            data = []
            desired_amp = .2
            self.pstat.set_ie_range(11)
            print(self.pstat.ie_range())
            ratio = self.pstat.gstat_ratio(self.pstat.ie_range())
            print(ratio)
            needed_voltage = (desired_amp/ratio)
            print("The needed voltage is {} ".format( + needed_voltage))
            self.pstat.set_voltage(needed_voltage)
            while curve.running():
                  data = curve.acq_data()
                  x = data['time'][1:]
                  y = data['vf'][1:]
                  np.savetxt(file_name, data, delimiter = ',', header ='time (s), vf, vu, im, pwr, r, vsig, ach, temp, ie_range, overload, stop_test, stop_test2')
                  plt.scatter(x,y, color = 'black')
                  plt.pause(0.05)
                  time.sleep(.01)
            self.pstat.set_cell(False)
            if len(data) > 0:
                  return(data)
            else:
                  print("No Data found. You might want to check your stop at conditions")
            print("Done")
            plt.show(block = False)
            return data  


            
            
      



