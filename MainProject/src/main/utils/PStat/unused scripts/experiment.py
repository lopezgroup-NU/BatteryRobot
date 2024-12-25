#The parent class to all of the experiments
import sys
sys.path.append(r'C:\Users\ablack.GAMRY\Documents\Jupyter\Supporting\Release')
from toolkitcommon import *
from toolkitcurves import *
import UniversalGraph as Graph
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
from inspect import currentframe, getframeinfo
from matplotlib.widgets import Button
from enumerations import stop_ats, pwrmodes,cell_types
#Run_number seems unneeded, there is actually no point to know who is first. AE and READBOTHHALFCells should apply to every experiment there should be no case in which
#An experiment turns on both half cells then turns it off, or has working flip. 
class experiment():
    run_number = 0
    config_check = False
    def __init__(self):
        self.run_number = experiment.run_number
    def display_parameters(self):
        """As pickle files are hard to read this is how you can display all dictionary values."""
        dataframe = pd.DataFrame(list(self.dictionary.items()), columns =['Parameters', 'Values'])
        print(dataframe)
    def save_parameters(self, parameter_name, path):
            "Overloaded save_parameters that has the file directory"
            if type(parameter_name) != str:
                  print("Please input a string as a file name")
                  return
            if parameter_name == "Placeholder" :
                  parameter_name = self.file_name + '_parmaters.pickle'
            if not parameter_name.endswith('.pickle'):
                  parameter_name = parameter_name + '.pickle'
            with open(path+ '\\' + parameter_name,  'wb') as handle:
                  pickle.dump(self.dictionary, handle, protocol = pickle.HIGHEST_PROTOCOL)
    def load_parameters(self, path):
            """loads a dictionary from a pickle file and sets the instance variables to the loaded parameters """
            with open(path, 'rb') as handle:
                  unserialized_data = pickle.load(handle)
            self.dictionary = unserialized_data
            self.update_variables()
            self.check = False 
    def print_dictionary(self):
         print(self.dictionary)
    def increase_run_number(self):
          experiment.run_number = experiment.run_number + 1
    def get_file_name(self):
        return self.dictionary.get('file_name')
    def set_file_name(self, value: str):
          if isinstance(value, str): 
            if (len(os.path.splitext(value)[-1]) ==0):
                 value = value + ".csv"
            self.dictionary.update({'file_name' : value})
          else:
                errormessage = "The file name that you entered is invalid. It should be a string. The previous value of {} will be used".format(self.file_name)
                result = ctypes.windll.user32.MessageBoxW(0,errormessage, "Error", 0x30 | 0x0)
