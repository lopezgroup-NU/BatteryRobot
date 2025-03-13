import time
import pandas as pd
from sympy import symbols, Eq, solve

def get_time_stamp():
    """
    Convert current time to string format
    """
    s = time.localtime(time.time())
    return time.strftime("%Y-%m-%d %H:%M:%S", s)

def get_water_weight_from_components(components_dict):
    """
    Wrapper for get_water_weight if input is a components_dict similar
    to what you would see in the DB
    """
    fsic, clo4c, tfsic, no3c, so4c, acc = 0, 0, 0, 0, 0, 0

    for component in components_dict:
        if component.upper() == "FSI":
            fsic = components_dict[component]
        elif component.upper() == "CLO4":
            clo4c = components_dict[component]
        elif component.upper() == "TFSI":
            tfsic = components_dict[component]
        elif component.upper() == "NO3":
            no3c = components_dict[component]            
        elif component.upper() == "SO4":
            so4c = components_dict[component]
        elif component.upper() == "AC":
            acc = components_dict[component]

    return get_weights(tfsic, fsic, no3c, clo4c, so4c, acc)

def get_weights(tfsic=0, fsic=0, no3c=0, clo4c=0, so4c=0, acc=0):
    """
    Solve for weights, does not return water
    """
    FSImm = 187.07
    ClO4mm = 106.39
    TFSImm = 287.09
    NO3mm = 68.946
    SO4mm = 109.94
    ACmm = 65.98
    TFSIp = .857520661
    FSIp = 0.79636725
    ClO4p = 0.346995275
    NO3p = 0.325782093
    SO4p = 0.249542221
    ACp = 0.315452965
    TFSId = 1.712394029
    FSId = 1.717983022
    ClO4d = 1.254605252
    NO3d = 1.246386555
    SO4d = 1.110433333
    ACd = 1.197393443
    # Define variables
    a, b, c, x, y, z, w = symbols('a b c x y z w')
    # Define equations
    eq2 = Eq(tfsic/1000, (x * TFSIp * TFSId) / (TFSImm* w))
    eq1 = Eq(fsic/1000, (y *FSIp  * FSId) / (FSImm* w))
    eq4 = Eq(no3c/1000, (z * NO3p * NO3d) / (NO3mm * w))
    eq3 = Eq(clo4c/1000, (a * ClO4p  * ClO4d) / (ClO4mm * w))
    eq5 = Eq(so4c/1000, (b * SO4p *  SO4d) / (SO4mm * w))
    eq6 = Eq(acc/1000, (c * ACp  * ACd) / (ACmm  * w))
    eq7 = Eq(w, 5 - x - y - z - a - b - c + (1 - ClO4p) * a * ClO4d + (1 - FSIp) * y *FSId + (1 - TFSIp) * x * TFSId + (1 - NO3p) * z * NO3d + (1 - SO4p) * b * SO4d + (1 - ACp) * c * ACd )
    #Solve the system of equations
    solution = solve((eq1, eq2, eq3, eq4, eq5, eq6, eq7), (a, b, c, x, y, z, w))
    return [solution[x], solution[y] , solution[z], solution[a], solution[b] , solution[c]]
