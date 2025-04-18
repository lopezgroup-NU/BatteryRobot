# file for processing any data that's already logged in to the spreadsheet
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import pandas as pd
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
    print(switch_x[0][0], "V", i , f"i0 = {params[0]:.3e}, alpha_c = {params[1]:.5f}")
