import pandas as pd
from sympy import symbols, Eq, solve

def read_formulation(file):
    """
    Take in csv file path of formulations, determine water weight
    Write new column to given file
    """

    df = pd.read_csv(file)
    df["water_weight"] = df.apply(
        lambda row: get_water_weight(
            row["LiFSI"],
            row["LiClO4"],
            row["LiTFSI"],
            row["LiNO3"],
            row["Li2SO4"],
            row["LiOAc"]
        ),
        axis=1
    )

    df.to_csv(file)

def get_water_weight(fsic, clo4c, tfsic, no3c, so4c, acc):
    """
    Solve for water weight 
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
    eq1 = Eq(fsic, (y *FSIp  * FSId) / (FSImm* w))
    eq2 = Eq(tfsic, (x * TFSIp * TFSId) / (TFSImm* w))
    eq3 = Eq(clo4c, (a * ClO4p  * ClO4d) / (ClO4mm * w))
    eq4 = Eq(no3c, (z * NO3p * NO3d) / (NO3mm * w))
    eq5 = Eq(so4c, (b * SO4p *  SO4d) / (SO4mm * w))
    eq6 = Eq(acc, (c * ACp  * ACd) / (ACmm  * w))
    eq7 = Eq(w, 5 - x - y - z - a - b - c + (1 - ClO4p) * a * ClO4d + (1 - FSIp) * y *FSId + (1 - TFSIp) * x * TFSId + (1 - NO3p) * z * NO3d + (1 - SO4p) * b * SO4d + (1 - ACp) * c * ACd )
    #Solve the system of equations
    solution = solve((eq1, eq2, eq3, eq4, eq5, eq6, eq7), (a, b, c, x, y, z, w))
    return solution[w]