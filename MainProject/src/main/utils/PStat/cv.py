import pandas as pd
from temper_windows import TemperWindows
import time
import toolkitpy as tkp
import time as Time
import datetime
import numpy as np
from .experiment import Experiment
from ..MathUtils import kinetic_fit
from pathlib import Path

import logging

# plate_gui installs a callable here: LIVE_HOOK(kind, x, y). Routed by thread identity.
LIVE_HOOK = None

import threading
_tkp_lock = threading.Lock()
def _ensure_tkp(name="cv.py"):
    with _tkp_lock:
        if not getattr(tkp, "_battery_tkp_initialized", False):
            tkp.toolkitpy_init(name)
            tkp._battery_tkp_initialized = True


#A modular rerunnable experiment according to given parameters.
class CV(Experiment):
    def __init__(self, voltage_list : list, scanrates : list, holdtimes : list, maxcycles : int, sample_period : float, PSTATMODE : tkp.CTRLMODE, guilherme_mode = False, **kwargs):
        """This class creates a Cyclic voltammetry experiment

        Parameters
        ------------

        voltage_list : list(float)
             List of voltages to be used in the CV [Vinit,V1,V2,Vfinal]

        scanrates : list(float)
            List of scan rates to be used in the CV [Vinit -> V1,V1 -> V2,V2 -> Vfinal]

        holdtimes : list(float)
            List of hold times to be used in the CV [Apex1, Apex2, Final]

        Sample Period : float
            Time between data-acquisition steps in seconds

        Max Cycle(int):
            Number of cycles for the CV

        CtrlMode(Enumeration:CTRLMODE):
             Potentiostat control mode. GSTATMODE or PSTATMODE

        guilherme_mode : bool
            True  -> low-current cells: +/-75 uA hardware I-stops, ie_range 8.
            False -> normal (mA-scale) cells: NO hardware I-stops, ie_range 10;
                     protection is the |Vf| > 3 V guard in run_cv.

        **kwargs
            As of right now Kwargs are the stop at conditions for each curve. The compatible stop ats for CV experiments are:
                "vmax"
                "vmin"
            """

        self.voltage_list = voltage_list
        self.scanrates = scanrates
        self.holdtimes = holdtimes
        self.sample_time = sample_period
        self.maxcycles = maxcycles
        self.PSTATMODE = PSTATMODE
        # FIX (merge damage): this line and the guilherme_mode param were dropped from
        # __init__ while every method still read self.guilherme_mode -> AttributeError.
        self.guilherme_mode = guilherme_mode
        super().__init__(kwargs)
        print(kwargs)

    def dc_105_initialize_pstat(self, pstat, sampling_rate):
            """This function is the standard initialization for DC experiments

            Parameters
            ----------
            pstat : toolkitpy.Pstat
                The desired pstat to change the hardware parameters
            sampling_rate : float
                The desired sampling rate of the experiment
            """
            pstat.set_cell(False)
            pstat.set_ach_select (tkp.ACHSELECT_GND)
            pstat.set_ctrl_mode(tkp.PSTATMODE)
            pstat.set_ie_stability (tkp.STABILITY_NORM)
            pstat.set_ca_speed(tkp.CASPEED_NORM)
            pstat.set_sense_speed (tkp.SENSE_SLOW)
            pstat.set_sense_speed_mode(False)
            pstat.set_ground(tkp.FLOAT)
            pstat.set_ich_range(3.0)
            pstat.set_ich_range_mode(False)
            pstat.set_ich_offset_enable(False)
            pstat.set_vch_range(10.0)
            pstat.set_vch_range_mode(True)
            pstat.set_vch_offset_enable(False)
            pstat.set_ach_range(3.0)
            pstat.set_ie_range_lower_limit(0)
            pstat.set_ie_range(8 if self.guilherme_mode else 10)
            pstat.set_pos_feed_enable(False)
            pstat.set_ie_range_mode(True)
            pstat.set_analog_out(0.0)
            pstat.set_voltage(0.0)
            pstat.set_dds_enable(False)
            pstat.set_vch_filter(1.0/sampling_rate)
            pstat.set_ich_filter(1.0/sampling_rate)

    def estimated_total_time(self):
        return self.estimated_point_count() * self.sample_time

    def estimated_point_count(self):
        """Total number of data points for the CV (all cycles)."""
        SignalPoints0 = int(abs(self.voltage_list[1] - self.voltage_list[0])/(self.sample_time * self.scanrates[0]) + .5)
        SignalPoints1 = int((self.holdtimes[0]/(self.sample_time)) + 0.5)
        SignalPoints2 = int(abs(self.voltage_list[2] - self.voltage_list[1])/(self.sample_time * self.scanrates[0]) + .5)
        SignalPoints3 = int(abs(self.holdtimes[1] / self.sample_time) + 0.5)
        SignalPoints4 = int(abs((self.voltage_list[3] - self.voltage_list[2]) / (self.sample_time * self.scanrates[0])) + 0.5)
        SignalPoints5 = int((self.holdtimes[2] / self.sample_time) + 0.5)
        per_cycle = SignalPoints0 + SignalPoints1 + SignalPoints2 + SignalPoints3 + SignalPoints4 + SignalPoints5
        return round(per_cycle * self.maxcycles)

    def run_cv(self, pstat, max_size = 100000):
        """Runs the triangle wave experiment. A Cyclic voltammogram if in pstatmode, otherwise a galvanodynamic triangle wave

        Parameters
        ----------
        pstat : tkp.PSTAT
            The potentiostat that will be used to generate the wave form
        max_size : int, optional
            The max size of the NumPy array used to store the data. Make sure this is greater than the
            estimated point count. The default is 100000.

        Returns
        -------
        NumPy ND array
            Returns an ND array with the data of the experiment
        """

        pstat.set_ctrl_mode(self.PSTATMODE)
        self.initialize_pstat(pstat)
        curve = tkp.RcvCurve(pstat, max_size)

        self.filter_stop_ats(curve, self.PSTATMODE)
        self.set_stop_ats(curve)
        signal = pstat.signal_r_up_dn_new(self.voltage_list, self.scanrates, self.holdtimes, self.sample_time, self.maxcycles, self.PSTATMODE)
        pstat.set_signal_r_up_dn(signal)
        self.set_stop_ats(curve)
        pstat.set_cell(True)
        points = self.estimated_point_count()
        total_time = self.estimated_total_time()
        i_limit = 0.000075 if self.guilherme_mode else 0.001
        # FIX: I-stops were truncating normal CVs mid-sweep ("only ran 1 voltage") and can never
        # match Framework traces on conductive cells. Keep them only for guilherme_mode's
        # deliberate 75 uA limit; normal runs rely on the |Vf| > 3 V guard below.
        if self.guilherme_mode:
            curve.set_stop_i_min(True, -1*i_limit)
            curve.set_stop_i_max(True, i_limit)

        class OverVoltageError(Exception):
            pass

        tkp.log.info(f"Running CV experiment there will be ~{points} rows of data and the experiment will take {total_time} seconds")
        curve.run(True)
        try:
            while curve.running():
                Time.sleep(1)
                data = curve.last_data_point()
                point = data['point']
                voltage = data['vf']
                current = data['im']
                if LIVE_HOOK: LIVE_HOOK("CV", voltage, current)
                tkp.log.info(f'Point {point + 1} of {points}\nVoltage: {voltage:.4f} voltage\nCurrent: {current:.5f} Amps')

                if abs(voltage) > 3:
                    print("---Excessive voltage detected! Stopping CV test---")
                    raise OverVoltageError("|Vf| > 3 V")
        finally:
            pstat.set_cell(False)   # cell goes off on every exit, including exceptions

        data = curve.acq_data()
        if data['stop_test'][-1] != 0:
            print(f"*** CV stop-at tripped (i_limit {i_limit} A) -- sweep truncated")
            tkp.log.info(f'Stop test occurred at point {data["point"][-1]}')  # FIX: last point, not the whole array
        print("Cyclic Voltammetry completed")
        self.is_run = True
        if self.PSTATMODE == tkp.PSTATMODE:
            self.last_value = data['vf'][-1]
        elif self.PSTATMODE == tkp.GSTATMODE:
            self.last_value = data['im'][-1]
        return data

    # Back-compat: old callers used run_cv_test; there is exactly one runner now.
    run_cv_test = run_cv

    def initialize_pstat(self, pstat):
        """This function changes the configuration of your pstat
        """
        #These will be some of the Framework parameters
        if self.PSTATMODE == tkp.PSTATMODE:
            pstat.set_ach_select(tkp.ACHSELECT_GND)
            pstat.set_ie_stability(tkp.STABILITY_NORM)
            pstat.set_ca_speed(tkp.CASPEED_NORM)
            pstat.set_ground(tkp.FLOAT)
            pstat.set_ich_range(3.0)
            pstat.set_ich_range_mode(False)
            pstat.set_ich_offset_enable(False)
            pstat.set_vch_range(10.0)
            pstat.set_vch_range_mode(True)
            pstat.set_vch_offset_enable(False)
            pstat.set_ach_range(3.0)
            pstat.set_ie_range_lower_limit(0) #For none
            pstat.set_ie_range(8 if self.guilherme_mode else 10)
            pstat.set_ie_range_mode(True)
            # FIX: set filters explicitly otherwise CV inherits PEIS's ~3 Hz filters
            pstat.set_vch_filter(1.0/self.sample_time)
            pstat.set_ich_filter(1.0/self.sample_time)
            pstat.set_pos_feed_enable(False)
            pstat.set_analog_out(0.0)
            pstat.set_voltage(0.0)
            pstat.set_pos_feed_resistance(0.0)
            pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
        else:
            self.dc_105_initialize_pstat(pstat, self.sample_time)
            pstat.set_PSTATMODE(tkp.GSTATMODE)
            pstat.set_stability(tkp.STABILITY_FAST)
            pstat.set_vch_range(10.0)
        return


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


def run_cv_output(output_file_name, values = [[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1], electrode_used = "Pt", save_to_db_folder = True, standard = False, guilherme_mode = True):
    """Vial-robot / single-pstat CV. Called by BatteryRobotUtils with guilherme_mode=g_mode."""

    _ensure_tkp("open_circuit_voltage.py")  # FIX: was tkp.toolkitpy_init on every call
    pstat = tkp.Pstat("PSTAT")
    cv = CV(values[0], values[1], values[2], values[3], values[4], tkp.PSTATMODE, imax = 10, guilherme_mode = guilherme_mode)
    data = cv.run_cv(pstat, max_size = 100000)

    if standard:
        out_path = "res/standard/cv/" + output_file_name + ".csv"
    else:
        out_path = "res/cv/" + output_file_name + ".csv"
    np.savetxt(out_path, data, delimiter = ',', header = 'Point,time,Vf,Vu,Im,Ach,vsig,temp,Cycle,ie_range,overload,stop_test', fmt = '%s')
    print("getting temp")
    # FIX: guard the dongle read -- an unguarded failure here threw away the whole run
    try:
        temper = TemperWindows(vendor_id=0x3553, product_id=0xa001) # long press caps lock
        temperature = temper.get_temperature()[1]
    except Exception as e:
        print("temp read failed: {}".format(e))
        temperature = float("nan")

    df = pd.read_csv(out_path, index_col='# Point')
    df['temp(C)'] = temperature
    df.to_csv(out_path)

    if save_to_db_folder and not standard:
        db_path = Path(r"C:\AttomRobotFiles\Data\DB_Missaka\cv") / f"{output_file_name}.csv"
        df.to_csv(db_path)

    if standard:
        s_df_file = "res/standard/std_cv_test_summaries.csv"
    else:
        s_df_file = "res/cv_test_summaries.csv"

    s_df = pd.read_csv(s_df_file)

    s = time.localtime(time.time())
    curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)

    try:
        vf_diff, vf_max, vf_min = cv_interpret(out_path)
    except Exception as e:
        print("cv_interpret failed on {}: {}".format(output_file_name, e))
        vf_diff = vf_max = vf_min = None
    # overP, i0, alpha_c = kinetic_fit(out_path)
    new_row = pd.DataFrame([[output_file_name, vf_max, vf_min, vf_diff, None, None, None, temperature, curr_time]], columns=['test name', 'vf_max', 'vf_min', 'vf_diff', "overP", "i0", "alpha_c", 'temp', 'time'])
    s_df = pd.concat([s_df, new_row], ignore_index=True)
    s_df.to_csv(s_df_file, index=False)

    if save_to_db_folder and not standard:
        return db_path

# Back-compat alias -- some newer code refers to this as run_cv2.
run_cv2 = run_cv_output


def run_cv_cell(cell, output_file_name = "chronovoltometry", values = [[1, 1.8, 1.08, 1], [0.01, 0.01, 0.01], [0.05, 0.05, 0.05], 2, 0.1], electrode_used = "Pt", path_to_save_to = r"C:\AttomRobotFiles\Data\DB_Ciara\cv", save_to_db_folder = True, standard = False, potentials_to_hold = [[0,0]]):
    """Plate-rig CV on one cell (0-23). Returns a DataFrame; the caller (triplet.py)
    owns saving/metadata. output_file_name etc. kept for signature compatibility.
                                       [[voltagelist],[  scanrates  ],[   holdtimes   ], maxcycles, sample_period]"""

    _ensure_tkp("open_circuit_voltage.py")  # FIX: was tkp.toolkitpy_init on every call (24x per plate)
    device_list = tkp.enum_sections()

    imx_list = []
    pstat_list = []

    for device_name in device_list:
        tag = device_name[0:3]
        if tag == 'IMX':
            imx_list.append(device_name)
        elif tag == 'IFC':
            pstat_list.append(device_name)
        else:
            print(f"!!!!! Found a non IMX or IFC type device. It is called: {device_name}")
    mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
    imx_list.sort()
    pstat_list.sort()
    print(pstat_list)
    print(mux_pstat_index)
    if mux_pstat_index >= len(pstat_list):
        raise RuntimeError(
            f"cell {cell} needs plate pstat #{mux_pstat_index} but only {pstat_list} are visible "
            # f"(vial pstat {VIAL_PSTAT_SERIAL} excluded). Is a plate IFC1010 powered off / unplugged?"
        )

    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])
    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
    # FIX: close mux/pstat on every exit -- an exception here used to leak GamryCom
    # leases (DEVICE_IN_USE on the next run)
    try:
        mux.open()
        active_ch = cell - mux_pstat_index * 8
        for ch in range(8):
            if ch != active_ch:
                mux.set_off_mode(ch, tkp.MUX_CELL_LOCAL)
                mux.set_dac(ch, 0.0)
        for pair in potentials_to_hold:
            ch = pair[0] - mux_pstat_index * 8
            if 0 <= ch <= 7 and ch != active_ch:
                mux.set_dac(ch, pair[1])
            # else: that cell isn't on this block's mux -- skip it
        mux.set_cell(active_ch)

        cv = CV(values[0], values[1], values[2], values[3], values[4], tkp.PSTATMODE, imax = 10, guilherme_mode = False)
        data = cv.run_cv(pstat)
    finally:
        try:
            pstat.set_cell(False)
        except Exception:
            pass
        try:
            mux.close()
        except Exception:
            pass
        try:
            pstat.close()
        except Exception:
            pass

    df = pd.DataFrame(data)

    # FIX: guard the dongle read -- an unguarded failure here threw away the whole run
    try:
        temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
        df["temp(C)"] = temper.get_temperature()[1]
    except Exception as e:
        print("temp read failed: {}".format(e))
        df["temp(C)"] = float("nan")
    df["datetime"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    return df


def cv_interpret(filename):
    df_file = filename
    df = pd.read_csv(df_file, index_col='# Point')

    positive, zero, negative = find_peaks_and_zero_crossings(df)

    targ_max = 0.000024
    targ_min = -0.000024

    im_col = df["Im"]
    im_colPositive = im_col[0:positive]
    im_colNegative = im_col[zero:negative]

    vf_col = df["Vf"]
    vf_colPositive = vf_col[0:positive]
    vf_colNegative = vf_col[zero:negative]

    #get xmax
    #translate column by target and get absolute values. find index of minimum (closest to 0)
    im_col_translated_pos = (im_colPositive - targ_max).abs()
    min_idx_pos = im_col_translated_pos.idxmin()
    vf_max = vf_colPositive.loc[min_idx_pos]  # Use .loc to get the value at that index

    #get xmin
    im_col_translated_neg = (im_colNegative + targ_max).abs()
    min_idx_neg = im_col_translated_neg.idxmin()
    vf_min = vf_colNegative.loc[min_idx_neg]  # Use .loc to get the value at that index

    vf_diff = vf_max - vf_min

    return (vf_diff, vf_max, vf_min)

'''
if __name__ == "__main__":
    tkp.toolkitpy_init("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    cv = CV([0, 1, -1, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1, tkp.PSTATMODE, imax = 10)
    data = cv.run_cv(pstat)
    np.savetxt("test.csv", data, delimiter = ',', header = 'Point, time, Vf, Vu, Im, Ach, vsig, temp, Cycle, ie_range, overload, stop_test', fmt = '%s')
'''