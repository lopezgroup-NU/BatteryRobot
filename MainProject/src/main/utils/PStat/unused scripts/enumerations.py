from enum import Enum
"""This file contains all of the enumerations for every experiment"""
class stop_ats(Enum):
    PWR_STOP_AVMAXSTOP = 1
    PWR_STOP_VMAXSTOP = 2
    PWR_STOP_VMINSTOP = 3
    PWR_STOP_AVMINSTOP = 4
    NoStop = 5
class pwrmodes(Enum):
    PWR_CURRENT_DISCHARGE = 1
    PWR_MODE_RESISTANCE = 2
    PWR_MODE_POWER = 3
    PWR_MODE_VOLTAGE = 4
    PWR_MODE_CURRENT_CHARGE = 5
    PWR_MODE_VOLTAGE_PSTATMODE = 6
    PWR_MODE_DISCHARGE_CRATEMULT = 7 
    PWR_MODE_DISCHARGE_CRATEDIV = 8
    PWR_MODE_CHARGE_CRATEMULT = 9
    PWR_MODE_CHARGE_CRATEDIV = 10
class EIS(Enum):
    READZ_SPEED_FAST = 1
    READZ_SPEED_NORM = 2
    READZ_SPEED_LOW = 3
class optimizeFor(Enum):
    FAST = 1
    NORMAL = 2 
    LOW_NOISE = 3
class loop_end(Enum):
    LOOP_END_DISCHARGETIMEUNDER = 1
    LOOP_END_CHARGETIMEOVER = 2
    LOOP_END_CAPACITYUNDERLIMIT = 3 
    NoEnd = 4
class cell_types(Enum):
    CELL_TYPE_FULL = 1
    CELL_TYPE_HALF = 2
    CELL_TYPE_BOTH = 3

    



    
    

    
    
    
    