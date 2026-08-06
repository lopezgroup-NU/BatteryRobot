import toolkitpy as tkp
import datetime
import math
import time
import numpy as np
import pandas as pd
from pathlib import Path
from temper_windows import TemperWindows

# FIX: MongoQuery no longer exists in DBUtils -- the old import made this module
# fail to import at all. (geis.py line 11 has the same dead import.)
# FIX: matplotlib/pyplot + use('TkAgg') removed -- every plot call was commented
# out, and stray pyplot windows create their own Tk root (the _default_root=None
# crash in the GUI).

# plate_gui installs a callable here: LIVE_HOOK(kind, x, y). Routed by thread identity.
LIVE_HOOK = None

from .cv import _ensure_tkp

def check_eis_points(initial_freq, final_freq, points_per_decade):
    #Calculate the number of points for an EIS curve.
    init_log = False
    final_log = False
    if abs(math.log10(initial_freq)) == float(math.floor(abs(math.log10(initial_freq)))):
        init_log = True

    if abs(math.log10(final_freq)) == float(math.floor(abs(math.log10(final_freq)))):
        final_log = True

    if init_log == True and final_log == True:
        factor = 0
    else:
        factor = 1

    preround = 0.50 + abs(math.log10(final_freq) - math.log10(initial_freq)) * points_per_decade
#Python does a round to even or bankers round. Therefore to deal with this we have to manually round.
#To read more about this: https://stackoverflow.com/questions/43851273/how-to-round-float-0-5-up-to-1-0-while-still-rounding-0-45-to-0-0-as-the-usual

    if (float(preround) % 1) >= .5:
        rounded = math.ceil(preround)
    else:
        rounded = round(preround, 0)
    result = int(factor + rounded)
    return result


# FIX: this used to be defined TWICE -- a second copy sat below the __main__
# block and silently overrode this one at import time. Single definition now.
def initialize_pstat(pstat):
     #These settings mirror the Galvanostatic EIS explain scripts.
     pstat.set_cell(False)
     pstat.set_ach_select(tkp.ACHSELECT_GND)
     pstat.set_ie_stability(tkp.STABILITY_FAST)
     pstat.set_ca_speed(tkp.CASPEED_NORM)
     pstat.set_ground(tkp.FLOAT)
     pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
     pstat.set_ich_range(3.0)
     pstat.set_ich_range_mode(False)
     pstat.set_ich_filter(3.0)
     pstat.set_vch_range(3.0)
     pstat.set_vch_range_mode(False)
     pstat.set_ich_offset_enable(True)
     pstat.set_vch_offset_enable(True)
     pstat.set_vch_filter(2.50)
     pstat.set_ach_range(3.0)
     pstat.set_ie_range(0.03)
     pstat.set_ie_range_mode(False)
     pstat.set_ie_range_lower_limit(0)
     pstat.set_analog_out(0.0)
     pstat.set_pos_feed_enable(False)
     pstat.set_irupt_mode(tkp.IRUPTOFF)


def run_peis(output_file_name = "potentiostatic_eis", parameter_list = None, save_to_db_folder = True, standard = False):
    """Legacy single-pstat PEIS (no MUX). Writes CSVs + summary row like it always did."""
    parameter_list = parameter_list or {}
    _ensure_tkp("potentiostatic_eis.py")
    pstat = tkp.Pstat("PSTAT")
    #Parameters
    #------------------------------------------------------------------
    initial_freq = parameter_list.get("initial_freq", 20000)     #Hz
    final_freq = parameter_list.get("final_freq", 1)             #Hz
    ac_voltage = parameter_list.get("ac_voltage", 0.01)          #V
    dc_voltage = parameter_list.get("dc_voltage", 0.0)           #V
    estimated_z = parameter_list.get("estimated_z", 100)         #ohm
    points_per_decade = parameter_list.get("points_per_decade", 10)  # none

    # internal state - pre 1st measurement
    gain = 1.0
    inoise = 0.0
    vnoise = 0.0
    ienoise = 0.0

    #-----------------------------------------------------------
    final_freq = abs(final_freq)
    initial_freq = abs(initial_freq)

    freq_lim_lower = pstat.freq_limit_lower()
    freq_lim_upper = pstat.freq_limit_upper()
    if(initial_freq > freq_lim_upper):
        print("Inital frequency exceeds upper frequency limit")
        initial_freq = freq_lim_upper
    if(final_freq > freq_lim_upper):
        final_freq = freq_lim_upper
        print("Final frequency exceeds upper frequency limit")
    if(initial_freq < freq_lim_lower):
        initial_freq = freq_lim_lower
        print("Inital frequency exceeds lower frequency limit")
    if(final_freq < freq_lim_lower):
        final_freq = freq_lim_lower
        print("Final frequency exceeds lower frequency limit")

    #==========================================
    initialize_pstat(pstat)
    pstat.set_ctrl_mode(tkp.PSTATMODE)
    pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
    Sdc = dc_voltage
    Sac = ac_voltage
    pstat.set_voltage(Sdc)
    pstat.set_cell(tkp.CELL_ON)
    dc_current = pstat.measure_i()
    ac_current = ac_voltage / max(abs(estimated_z), 1e-6)   # I = V/Z (was Z*V, dimensionally wrong)
    ie_range = pstat.test_ie_range(abs(dc_current) + 1.414*abs(ac_current))
    pstat.set_ie_range(ie_range)

    readz = tkp.ReadZ(pstat)
    readz.set_gain(gain)
    readz.set_inoise(inoise)
    readz.set_vnoise(vnoise)
    readz.set_ienoise(ienoise)
    readz.set_zmod(estimated_z)
    readz.set_vdc(dc_voltage)
    readz.set_speed(1) #Normal
    readz.set_drift_cor(False)
    readz.set_idc(dc_current)

    #==========================================
    log_increment = 1.0/points_per_decade
    if initial_freq > final_freq:
        log_increment = -log_increment
    # FIX: was tkp.check_eis_points -- toolkitpy doesn't export it; use the local one
    max_points = check_eis_points(initial_freq, final_freq, points_per_decade)
    zcurve = tkp.ZCurve(max_points)

    current_points = 0
    try:
        while current_points < max_points:
            freq = math.pow(10.0, math.log10(initial_freq) + current_points * log_increment)
            status = readz.Measure(freq, ac_voltage, dc_voltage)
            if status == False:
                print('Bad Value.')
                current_points += 1
                continue
            else:
                zcurve.add_point(readz)
            current_points += 1
            time.sleep(0.010)
    finally:
        pstat.set_cell(False)

    if standard:
        out_path = "res/standard/peis/" + output_file_name + ".csv"
    else:
        out_path = "res/peis/" + output_file_name + ".csv"
    np.savetxt(out_path, zcurve.acq_data(), delimiter = ',',
               header = 'point,freq,zreal,zimag,zmod,zphz,zsig,Idc,Vdc,ie_range,gain,vmod,vphz,vsig,vthd,imod,iphz,isig,ithd,zreal_drift,zimag_drift,zmod_drift,zphz_drift')

    # FIX: guard the dongle read -- an unguarded failure here threw away the whole run
    try:
        temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
        temperature = temper.get_temperature()[1]
    except Exception as e:
        print("temp read failed: {}".format(e))
        temperature = float("nan")
    today = datetime.datetime.now()
    formatted_date = today.strftime("%Y/%m/%d %H:%M:%S")  #Year/Month/Day Hour:Minute:Second

    df = pd.read_csv(out_path, index_col='# point')
    reflected_zimag = [-val for val in df['zimag']]
    df.insert(2, 'reflected_zimag', reflected_zimag)
    df['temp(C)'] = temperature
    df['datetime'] = formatted_date

    df.to_csv(out_path)
    if save_to_db_folder and not standard:
        db_path = Path(r"C:\AttomRobotFiles\Data\DB_Ciara\peis") / f"{output_file_name}.csv"
        df.to_csv(db_path)

    # extract minima
    if standard:
        s_df_file = "res/standard/std_peis_test_summaries.csv"
    else:
        s_df_file = "res/peis_test_summaries.csv"
    s_df = pd.read_csv(s_df_file)
    df_no_negatives = df[df.reflected_zimag >= 0]
    min_index = df_no_negatives['reflected_zimag'].idxmin()  # Get the index of the minimum value
    R1_nofit = df_no_negatives['zreal'].loc[min_index]  # Use .loc to get the value at that index
    R1 = 10
    s = time.localtime(time.time())
    curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)
    new_row = pd.DataFrame([[output_file_name, R1, R1_nofit, temperature, curr_time]], columns=['test name', 'zreal', 'minima', 'temp', 'time'])

    s_df = pd.concat([s_df, new_row], ignore_index=True)
    s_df.to_csv(s_df_file, index=False)

    if save_to_db_folder and not standard:
        return db_path, zcurve

    return zcurve


def run_peis_cell(cell, output_file_name = "potentiostatic_eis", parameter_list = None, save_to_db_folder = True, standard = False):
    """Run one PEIS sweep on `cell` (0-23) through its block's MUX + pstat and return
    the curve as a DataFrame. Nothing is written to disk here (the caller owns storage).

    `output_file_name`, `save_to_db_folder`, and `standard` are accepted so existing
    callers don't break, but they are unused now that this function doesn't write files.
    """
    parameter_list = parameter_list or {}

    if not 0 <= cell <= 23:
        raise ValueError(f"cell must be 0-23, got {cell}")

    _ensure_tkp("potentiostatic_eis.py")  # FIX: was tkp.toolkitpy_init on every call
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
            print(f"!!!!! Found a non-IMX or IFC type device. It is called: {device_name}")

    imx_list.sort()
    pstat_list.sort()
    mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
    if mux_pstat_index >= len(pstat_list) or mux_pstat_index >= len(imx_list):
        raise RuntimeError(
            f"cell {cell} needs pstat/mux #{mux_pstat_index} but visible devices are "
            f"pstats={pstat_list}, muxes={imx_list} (vial pstat {VIAL_PSTAT_SERIAL} excluded). "
            f"Is that block powered / plugged in?")
    print(pstat_list)
    print(mux_pstat_index)

    #Parameters -- every key optional via .get(), so a missing key can never crash mid-run
    #------------------------------------------------------------------
    initial_freq = abs(parameter_list.get("initial_freq", 5000))     #Hz
    final_freq = abs(parameter_list.get("final_freq", 10))           #Hz
    ac_voltage = parameter_list.get("ac_voltage", 0.02)              #V
    dc_voltage = parameter_list.get("dc_voltage", 0.0)               #V
    estimated_z = parameter_list.get("estimated_z", 100)             #ohm
    points_per_decade = parameter_list.get("points_per_decade", 10)  # none
    MAX_TRIES = int(parameter_list.get("max_bad_reads", 3))          # attempts per frequency point

    # internal state - pre 1st measurement
    gain = 1.0
    inoise = 0.0
    vnoise = 0.0
    ienoise = 0.0

    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])
    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])

    steps = []                                   # (freq, ok) per commanded point
    # FIX: the try now starts at mux.open() -- previously the mux was opened and the
    # cell energized BEFORE the try, so a failure during setup leaked both devices
    # ("In use by another script" on the next run).
    try:
        mux.open()
        active_ch = cell - mux_pstat_index * 8
        for ch in range(8):                              # 8 channels on this MUX
            if ch != active_ch:
                mux.set_off_mode(ch, tkp.MUX_CELL_LOCAL) # isolate inactive channels to their local DAC
                mux.set_dac(ch, dc_voltage)              # hold them at a safe potential (your OCV / 0)
        mux.set_cell(active_ch)

        final_freq = abs(final_freq)
        initial_freq = abs(initial_freq)

        freq_lim_lower = pstat.freq_limit_lower()
        freq_lim_upper = pstat.freq_limit_upper()
        if(initial_freq > freq_lim_upper):
            print("Inital frequency exceeds upper frequency limit")
            initial_freq = freq_lim_upper
        if(final_freq > freq_lim_upper):
            final_freq = freq_lim_upper
            print("Final frequency exceeds upper frequency limit")
        if(initial_freq < freq_lim_lower):
            initial_freq = freq_lim_lower
            print("Inital frequency exceeds lower frequency limit")
        if(final_freq < freq_lim_lower):
            final_freq = freq_lim_lower
            print("Final frequency exceeds lower frequency limit")

        #==========================================
        initialize_pstat(pstat)
        pstat.set_ctrl_mode(tkp.PSTATMODE)
        pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
        Sdc = dc_voltage
        Sac = ac_voltage
        pstat.set_voltage(Sdc)
        pstat.set_cell(tkp.CELL_ON)
        dc_current = pstat.measure_i()
        ac_current = ac_voltage / max(abs(estimated_z), 1e-6)   # I = V/Z (was Z*V, dimensionally wrong)
        ie_range = pstat.test_ie_range(abs(dc_current) + 1.414*abs(ac_current))
        pstat.set_ie_range(ie_range)

        readz = tkp.ReadZ(pstat)
        readz.set_gain(gain)
        readz.set_inoise(inoise)
        readz.set_vnoise(vnoise)
        readz.set_ienoise(ienoise)
        readz.set_zmod(estimated_z)
        readz.set_vdc(dc_voltage)
        readz.set_speed(1) #Normal
        readz.set_drift_cor(False)
        readz.set_idc(dc_current)

        #==========================================
        log_increment = 1.0/points_per_decade
        if initial_freq > final_freq:
            log_increment = -log_increment
        max_points = check_eis_points(initial_freq, final_freq, points_per_decade)
        zcurve = tkp.ZCurve(max_points)

        step = 0
        while step < max_points:
            freq = math.pow(10.0, math.log10(initial_freq) + step * log_increment)
            ok = False
            for attempt in range(1, MAX_TRIES + 1):
                if readz.Measure(freq, ac_voltage, dc_voltage):
                    ok = True
                    break
                print(f"Bad value at {freq:.1f} Hz (attempt {attempt}/{MAX_TRIES})")
                time.sleep(0.01)
            if ok:
                zcurve.add_point(readz)          # readz only has data on success
                if LIVE_HOOK:
                    try:
                        _d = zcurve.acq_data()
                        LIVE_HOOK("PEIS", _d['zreal'][zcurve.point - 1], -_d['zimag'][zcurve.point - 1])
                    except Exception:
                        pass
            steps.append((freq, ok))
            step += 1                            # ALWAYS advance to the next frequency
            time.sleep(0.01)
    finally:
        # Runs on success, on ANY exception above, and on Ctrl+C:
        # cell off first, then release both devices. Each step is guarded so one
        # failed cleanup can't block the others.
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

    n_bad = sum(1 for _, ok in steps if not ok)
    if n_bad:
        print(f"PEIS finished -- {n_bad} of {len(steps)} point(s) flagged bad.")

    # Build the DataFrame straight from the acquired curve -- no file round-trip.
    # readz can't store failed reads, so reconstruct full length: good rows come
    # from the curve in order, failed rows are NaN with the commanded frequency.
    n_good = sum(ok for _, ok in steps)
    zdata = pd.DataFrame(zcurve.acq_data()).iloc[:n_good].reset_index(drop=True)

    rows, gi = [], 0
    for freq, ok in steps:
        if ok:
            rows.append(zdata.iloc[gi]); gi += 1
        else:
            r = pd.Series(np.nan, index=zdata.columns)
            if "zfreq" in r.index:
                r["zfreq"] = freq                # keep the commanded freq on failed rows
            rows.append(r)
    df = pd.DataFrame(rows).reset_index(drop=True)
    df["bad_value"] = [0 if ok else 1 for _, ok in steps]
    if "zimag" in df.columns:
        df["reflected_zimag"] = -df["zimag"]

    # FIX: guard the dongle read and keep the column present (NaN) on failure,
    # matching cv.py, so downstream column expectations don't break
    try:
        temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
        df["temp(C)"] = temper.get_temperature()[1]
    except Exception as e:
        print("temp read failed: {}".format(e))
        df["temp(C)"] = float("nan")
    df["datetime"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    return df


if __name__ == "__main__":
    # FIX: this used to call run_peis(parameter_list) positionally, which shoved the
    # dict into output_file_name.
    parameter_list = {
        'initial_freq': 2000000.0,
        'final_freq': 2.0,
        'points_per_decade': 40,
        'estimated_z': 2000.0,
        'dc_voltage': 0.0,
    }
    zcurve = run_peis(parameter_list=parameter_list)