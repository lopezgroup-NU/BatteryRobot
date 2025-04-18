import time
import pandas as pd
from sympy import symbols, Eq, solve
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

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

    return get_wweights(tfsic, fsic, no3c, clo4c, so4c, acc)

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

def get_wweights(tfsic=0, fsic=0, no3c=0, clo4c=0, so4c=0, acc=0):
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
    return float(solution[w])

# Constants
F = 96485  # C/mol
R = 8.314  # J/mol·K
def butler_volmer(eta, j0, alphaC, n=2, T=298.15):
    #alpha A
    return j0 *  - np.exp(-(alphaC) * n * F * eta / (R * T))
def fit_butler_volmer(eta_data, current_data, T=298.15, n = 1, plot=False): #change name to tafel_fit
    """Fits the Butler-Volmer equation to experimental data."""
    def bv_fit_func(eta, i0, alphaC):
        return butler_volmer(eta, i0, alphaC, n=n, T=T)
    initial_guess = [1, 0.5]
    bounds = ([.00001, 0.0], [200, 1])
    popt, pcov = curve_fit(bv_fit_func, eta_data, current_data, p0=initial_guess, bounds=bounds,maxfev=500000)
    if plot:
        eta_fit = np.linspace(min(eta_data), max(eta_data), 500000)
        current_fit = bv_fit_func(eta_fit, *popt)
        fig, ax1 = plt.subplots()
        fig.patch.set_facecolor('white')
        # Primary Y-axis: log scale
        ax1.scatter(eta_data, np.log(np.abs(current_data)), color='k', label='Log Data')
        ax1.plot(eta_fit, np.log(np.abs(current_fit)), '-', label='Log Fit')
        ax1.set_xlabel('Overpotential (V)')
        ax1.set_ylabel('ln(|Current density|)', color='black')
        ax1.tick_params(axis='y', labelcolor='black')
        # Secondary Y-axis: linear scale
        ax2 = ax1.twinx()
        ax2.scatter(eta_data, current_data, color='r', label='Linear Data', alpha=0.6)
        ax2.plot(eta_fit, current_fit, '-', color='orange', label='Linear Fit', alpha=0.6)
        ax2.set_ylabel('Current density (mA/cm²)', color='orange')
        ax2.tick_params(axis='y', labelcolor='orange')
        return popt, pcov
def find_zero_crossings_from_lists(x_list, y_list):
    """
    Finds zero crossings in two parallel lists: x-values and y-values.
    Parameters:
        x_list (list of float): X-axis values (e.g., voltage).
        y_list (list of float): Y-axis values (e.g., current).
    Returns:
        List of (x, 0.0) points where the curve crosses the x-axis.
    """
    zero_crossings = []
    for i in range(len(y_list) - 1):
        x1, y1 = x_list[i], y_list[i]
        x2, y2 = x_list[i + 1], y_list[i + 1]
        # Check for sign change
        if y1 * y2 < 0:
            x_zero = x1 - y1 * (x2 - x1) / (y2 - y1)
            zero_crossings.append((x_zero, 0.0))
        elif y1 == 0:
            zero_crossings.append((x1, 0.0))
    return zero_crossings

def find_peaks_and_zero_crossings(data):
    # Find the index of the first occurrence of zero in 'Vf'
    zero_index = np.argmax(data['Vf'] >= 0)
    # Find the positive peak (maximum after the first zero crossing)
    positive_peak_index = np.argmax(data['Im'][zero_index:]) + zero_index
    # Find where the voltage crosses 0 after the positive peak
    # We are looking for the first zero-crossing point after the positive peak
    zero_cross_index = np.argmax(np.diff(np.sign(data['Vf'][positive_peak_index:])) != 0) + positive_peak_index
    # Find the negative peak (minimum after the 0V crossing)
    negative_peak_index = np.argmin(data['Im'][zero_cross_index:]) + zero_cross_index
    return positive_peak_index, zero_cross_index, negative_peak_index

files = []
results_column = []
def kinetic_fit(cv_file):
    data_first = pd.read_csv(cv_file)
    positive_peak_index, zero_cross_index, negative_peak_index = find_peaks_and_zero_crossings(data_first)
    E = data_first['Vf']
    I = data_first['Im']*1000/0.020
    E = E[negative_peak_index:]
    I = I[negative_peak_index:]
    fig2, ax3 = plt.subplots()
    ax3.plot(E,I, label = "All Data")
    ax3.set_xlabel('Potential (V)')
    ax3.set_ylabel('Current (mA/cm^2)')
    switch_x = find_zero_crossings_from_lists(E.to_numpy(), I.to_numpy())
    E = E  - switch_x[0][0]
    mask =  (E <= -.06)
    E = E[mask]
    I = I[mask]
    ax3.plot(E+switch_x[0][0],I, label = "To be fit")
    params, covariance = fit_butler_volmer(E, I, T=298.15, plot=True)
    return (switch_x[0][0], f"{params[0]:.3e}", f"{params[1]:.5f}")