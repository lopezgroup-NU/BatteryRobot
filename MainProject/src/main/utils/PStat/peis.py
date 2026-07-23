import sys
import toolkitpy as tkp
import datetime

from temper_windows import TemperWindows
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
import math
import matplotlib

import pandas as pd
from utils.DBUtils import MongoQuery
from pathlib import Path

from matplotlib import pyplot as plt          #Used to plot data
import os

LIVE_HOOK = None

matplotlib.use('TkAgg')

def check_eis_points(initial_freq, final_freq, points_per_decade):
    #Calculate the number of points for an EIS curve.
    init_log = False
    final_log = False
    if abs(math.log10(initial_freq)) == float(math.floor(abs(math.log10(initial_freq)))):
        init_log = True

    if abs(math.log10(final_freq)) == float(math.floor(abs(math.log10(final_freq)))):
        final_log = True

    if init_log  == True and final_log == True:
        factor = 0
    else:
        factor = 1

    preround = 0.50 + abs(math.log10(final_freq)-math.log10(initial_freq)) * points_per_decade
#Python does a round to even or bankers round. Therefore to deal with this we have to manually round. 
#To read more about this: https://stackoverflow.com/questions/43851273/how-to-round-float-0-5-up-to-1-0-while-still-rounding-0-45-to-0-0-as-the-usual

    if (float(preround) % 1) >= .5:
        rounded = math.ceil(preround)
    else: 
        rounded = round(preround, 0)
    result = int(factor + rounded)
    return result

def initialize_pstat(pstat):
     #These settings 494 Galvanostatic EIS in the explain scripts. 
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
     pstat.set_ich_range_mode(False)
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

def run_peis(output_file_name = "potentiostatic_eis", parameter_list = {}, save_to_db_folder = True, standard = False):
    tkp.toolkitpy_init("potentiostatic_eis.py")
    pstat = tkp.Pstat("PSTAT")
    #Parameters
    #------------------------------------------------------------------
    initial_freq = parameter_list.get("initial_freq", 20000)     #Hz
    final_freq = parameter_list.get("final_freq", 1)            #Hz
    ac_voltage = parameter_list.get("ac_voltage", 0.01)         #V
    dc_voltage = parameter_list.get("dc_voltage", 0.0)          #V
    estimated_z = parameter_list.get("estimated_z", 100)        #ohm
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
    ac_current = estimated_z * ac_voltage
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
    max_points = tkp.check_eis_points(initial_freq, final_freq, points_per_decade)
    zcurve = tkp.ZCurve(max_points)

    # fig, (ax, ax3) = plt.subplots(1,2, figsize = (12,10))
    # ax.set_xlabel("frequency")
    # ax.set_ylabel("Zmod")
    # ax2 = ax.twinx()
    # ax2.set_ylabel("Phase")
    # ax.set_xscale('log')
    # ax.set_yscale('log')
    # ax.set_ylim(100,1E6 )
    # ax2.set_ylim(-90,90)
    # ax.set_title("Bode")
    # ax3.set_title("Nyquist")
    # ax3.set_xlabel("Z real (ohm)")
    # ax3.set_ylabel("Z imiaginary (Ohm)")
    # added = True
    current_points = 0
    while current_points < max_points:
        freq = math.pow(10.0, math.log10(initial_freq) + current_points * log_increment)
        status = readz.Measure(freq, ac_voltage,dc_voltage)
        if status == False:
            print('Bad Value.')
            if status == 0:
                print('empty')
                continue
            elif status == 1:
                continue
            else:
                current_points += 1
                continue
            
        else:
            zcurve.add_point(readz)
            data = zcurve.acq_data()
            nextpoint = zcurve.point
            lastpoint = nextpoint-1

            # ax.scatter(data['zfreq'][:lastpoint], data['zmod'][:lastpoint], marker = '.', color = 'b',label = 'Mod')
            # ax2.scatter(data['zfreq'][:lastpoint], data['zphz'][:lastpoint], marker='.', color = 'k',label = 'Phase')
            # ax3.scatter(data['zreal'][:lastpoint], -data['zimag'][:lastpoint], marker = '.', color = 'b') 
            # if added:
            #      ax.legend()
            #      ax2.legend(loc = 'upper left' )
            #      added = False
            # ax.axhline(y=0, color = 'k', linestyle = ':')
            # plt.pause(0.05)
        current_points +=1
        
        time.sleep(0.010)

    pstat.set_cell(False)
    
    
    if standard:
        out_path = "res/standard/peis/" + output_file_name+ ".csv"
    else:
        out_path = "res/peis/" + output_file_name+ ".csv"
    np.savetxt(out_path, zcurve.acq_data(),delimiter = ',', 
               header = 'point,freq,zreal,zimag,zmod,zphz,zsig,Idc,Vdc,ie_range,gain,vmod,vphz,vsig,vthd,imod,iphz,isig,ithd,zreal_drift,zimag_drift,zmod_drift,zphz_drift')
    
    temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
    temperature = temper.get_temperature()[1]
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
    df_no_negatives = df[df.reflected_zimag >=0]
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

def run_peis_cell(cell, output_file_name = "potentiostatic_eis", parameter_list = {}, save_to_db_folder = True, standard = False):
    tkp.toolkitpy_init("potentiostatic_eis.py")

    device_list = tkp.enum_sections()

    #pstat_list_names = tkp.enum_sections()
    #print(pstat_list_names)
   
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

    mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
    imx_list.sort()
    pstat_list.sort()
    print(pstat_list)
    print(mux_pstat_index)
    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])
    # print(f"pstat upper frequency limit: {pstat.freq_limit_upper()}")
    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
    # mux.open()

    # mux.set_cell(cell-mux_pstat_index*8)

    #Parameters
    #------------------------------------------------------------------
    initial_freq = parameter_list.get("initial_freq", 5000)     #Hz
    final_freq = parameter_list.get("final_freq", 10)           #Hz
    ac_voltage = parameter_list.get("ac_voltage", 0.02)         #V
    dc_voltage = parameter_list.get("dc_voltage", 0.0)          #V
    estimated_z = parameter_list.get("estimated_z", 100)        #ohm
    points_per_decade = parameter_list.get("points_per_decade", 10)

    # internal state - pre 1st measurement
    gain = 1.0
    inoise = 0.0
    vnoise = 0.0
    ienoise = 0.0

    #-----------------------------------------------------------    
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
    # ac_current = estimated_z * ac_voltage
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

    # fig, (ax, ax3) = plt.subplots(1,2, figsize = (12,10))
    # ax.set_xlabel("frequency")
    # ax.set_ylabel("Zmod")
    # ax2 = ax.twinx()
    # ax2.set_ylabel("Phase")
    # ax.set_xscale('log')
    # ax.set_yscale('log')
    # ax.set_ylim(100,1E6 )
    # ax2.set_ylim(-90,90)
    # ax.set_title("Bode")
    # ax3.set_title("Nyquist")
    # ax3.set_xlabel("Z real (ohm)")
    # ax3.set_ylabel("Z imiaginary (Ohm)")
    # added = True

    # MAX_TRIES = parameter_list.get("max_bad_reads", 1)
    # MAX_TRIES = parameter_list["max_bad_reads"]
    # skipped = 0
    # step = 0
    # try:
    #     while step < max_points:
    #         freq = math.pow(10.0, math.log10(initial_freq) + step * log_increment)
    #         measured = False
    #         for attempt in range(1, MAX_TRIES + 1):
    #             if readz.Measure(freq, ac_voltage, dc_voltage): # good reading
    #                 zcurve.add_point(readz)
    #                 measured = True
    #                 break
    #             print(f"Bad value at {freq:.1f} Hz (attempt {attempt}/{MAX_TRIES})")
    #             time.sleep(0.01) # brief settle before retrying
    #         if not measured:
    #             print(f"Skipping {freq:.1f} Hz after {MAX_TRIES} bad attempts.")
    #             skipped += 1
    #         step += 1 # ALWAYS advance to the next frequency
    #         time.sleep(0.01)
    # finally:
    #     pstat.set_cell(False)
    #     try:
    #         mux.close()
    #     except Exception:
    #         pass
    # if skipped:
    #     print(f"PEIS finished -- {skipped} of {max_points} frequency point(s) skipped.")

    MAX_TRIES = int(parameter_list.get("max_bad_reads", 3))
    steps = []                                   # (freq, ok) per commanded point
    step = 0
    try:
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
            step += 1
            time.sleep(0.01)
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


    n_bad = sum(1 for _, ok in steps if not ok)
    if n_bad:
        print(f"PEIS finished -- {n_bad} of {max_points} point(s) flagged bad.")


    # current_points = 0
    # while current_points < max_points:
    #     freq = math.pow(10.0, math.log10(initial_freq) + current_points * log_increment)
    #     status = readz.Measure(freq, ac_voltage,dc_voltage)
    #     if status == False:
    #         print('Bad Value.')
    #         if status == 0:
    #             print('empty')
    #             continue
    #         elif status == 1:
    #             continue
    #         else:
    #             current_points += 1
    #             continue
            
    #     else:
    #         zcurve.add_point(readz)
    #         data = zcurve.acq_data()
    #         nextpoint = zcurve.point
    #         lastpoint = nextpoint-1

            # ax.scatter(data['zfreq'][:lastpoint], data['zmod'][:lastpoint], marker = '.', color = 'b',label = 'Mod')
            # ax2.scatter(data['zfreq'][:lastpoint], data['zphz'][:lastpoint], marker='.', color = 'k',label = 'Phase')
            # ax3.scatter(data['zreal'][:lastpoint], -data['zimag'][:lastpoint], marker = '.', color = 'b') 
            # if added:
            #      ax.legend()
            #      ax2.legend(loc = 'upper left' )
            #      added = False
            # ax.axhline(y=0, color = 'k', linestyle = ':')
            # plt.pause(0.05)
        # current_points +=1
        
        # time.sleep(0.010)

    # pstat.set_cell(False)
    
    
    # if standard:
    #     out_path = "res/standard/peis/" + output_file_name+ ".csv"
    # else:
    #     out_path = "res/peis/" + output_file_name+ ".csv"
    # np.savetxt(out_path, zcurve.acq_data(),delimiter = ',', 
    #            header = 'point,freq,zreal,zimag,zmod,zphz,zsig,Idc,Vdc,ie_range,gain,vmod,vphz,vsig,vthd,imod,iphz,isig,ithd,zreal_drift,zimag_drift,zmod_drift,zphz_drift')
    
    # temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
    # temperature = temper.get_temperature()[1]
    # today = datetime.datetime.now()
    # formatted_date = today.strftime("%Y/%m/%d %H:%M:%S")  #Year/Month/Day Hour:Minute:Second

    
    # df = pd.read_csv(out_path, index_col='# point')
    # reflected_zimag = [-val for val in df['zimag']]
    # df.insert(2, 'reflected_zimag', reflected_zimag)
    # df['temp(C)'] = temperature
    # df['datetime'] = formatted_date

    # df.to_csv(out_path)
    # #"C:\AttomRobotFiles\Data\DB_Missaka\eis"
    # if save_to_db_folder and not standard:
    #     db_path = Path(r"C:\AttomRobotFiles\Data\DB_Ciara\peis") / f"{output_file_name}.csv"
    #     df.to_csv(db_path) 

    # # extract minima
    # if standard:
    #     s_df_file = "res/standard/std_peis_test_summaries.csv"
    # else:
    #     s_df_file = "res/peis_test_summaries.csv"
    # s_df = pd.read_csv(s_df_file)
    # df_no_negatives = df[df.reflected_zimag >=0]
    # min_index = df_no_negatives['reflected_zimag'].idxmin()  # Get the index of the minimum value
    # R1_nofit = df_no_negatives['zreal'].loc[min_index]  # Use .loc to get the value at that index
    # R1 = 10
    # s = time.localtime(time.time())
    # curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)
    # new_row = pd.DataFrame([[output_file_name, R1, R1_nofit, temperature, curr_time]], columns=['test name', 'zreal', 'minima', 'temp', 'time'])

    # s_df = pd.concat([s_df, new_row], ignore_index=True)
    # s_df.to_csv(s_df_file, index=False)  

    # if save_to_db_folder and not standard:
    #     return db_path, zcurve

    # return zcurve

    # pstat.set_cell(False)

    # Build the DataFrame straight from the acquired curve — no file round-trip.
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
    
    # df = pd.DataFrame(zcurve.acq_data())
    # df["bad_flag"] = bad_flags
    # if "zimag" in df.columns:
    #     df["reflected_zimag"] = -df["zimag"]

    # # optional: keep the temperature + timestamp columns you had
    try:
        temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
        df["temp(C)"] = temper.get_temperature()[1]
    except Exception:
        pass
    df["datetime"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    return df


# def run_peis(cell: int, params: dict) -> tuple[pd.DataFrame, dict]:
    """
    Run one potentiostatic EIS sweep on `cell` (0-23) through its MUX and return
    (data, resolved_params). `data` is the impedance curve as a DataFrame.
    IMPORTANT: Nothing is written to disk here.
    """
    params = params or {}
    initial_freq      = abs(params.get("initial_freq", 20000))   # Hz
    final_freq        = abs(params.get("final_freq", 1))         # Hz
    ac_voltage          = params.get("ac_voltage", 0.01)           # V
    dc_voltage        = params.get("dc_voltage", 0.0)            # V
    estimated_z       = params.get("estimated_z", 100)           # ohm
    points_per_decade = params.get("points_per_decade", 10)

    tkp.toolkitpy_init("potentiostatic_eis.py")
    devices    = tkp.enum_sections()
    imx_list   = [d for d in devices if d[:3] == "IMX"]
    pstat_list = [d for d in devices if d[:3] == "IFC"]

    mux_index = 0 if cell < 8 else 1 if cell < 16 else 2
    pstat = tkp.Pstat("Pstat", pstat_list[mux_index])
    mux = tkp.IMX("IMX", imx_list[mux_index])
    mux.open()
    mux.set_cell(cell - mux_index * 8)

    lo, hi = pstat.freq_limit_lower(), pstat.freq_limit_upper()
    initial_freq = min(max(initial_freq, lo), hi)
    final_freq   = min(max(final_freq, lo), hi)

    initialize_pstat(pstat)
    pstat.set_ctrl_mode(tkp.PSTATMODE)
    pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
    pstat.set_voltage(dc_voltage)
    pstat.set_cell(tkp.CELL_ON)
    dc_current = pstat.measure_i()
    ac_current = estimated_z * ac_voltage
    pstat.set_ie_range(pstat.test_ie_range(abs(dc_current) + 1.414 * abs(ac_current)))

    readz = tkp.ReadZ(pstat)
    readz.set_gain(1.0)
    readz.set_inoise(0.0)
    readz.set_vnoise(0.0)
    readz.set_ienoise(0.0)
    readz.set_zmod(estimated_z)


# def run_peis_cell(cell, output_file_name = "potentiostatic_eis", parameter_list = None, save_to_db_folder = True, standard = False):
    """Run one PEIS sweep on `cell` (0-23) through its block's MUX + pstat and return the
    curve as a DataFrame. Nothing is written to disk here (the caller owns storage).
 
    `output_file_name`, `save_to_db_folder`, and `standard` are accepted so existing
    callers don't break, but they are unused now that this function doesn't write files.
 
    Device lifecycle (the important part): pstat + mux are opened INSIDE a try whose
    finally ALWAYS turns the cell off and closes BOTH devices -- on success, on any
    exception, and on Ctrl+C. No failure mode can leave a device locked
    ("In use by another script") or a cell energized.
    """
    parameter_list = parameter_list or {}
 
    if not 0 <= cell <= 23:
        raise ValueError(f"cell must be 0-23, got {cell}")
 
    tkp.toolkitpy_init("potentiostatic_eis.py")
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
            f"Cell {cell} needs pstat/mux #{mux_pstat_index}, but connected devices are "
            f"pstats={pstat_list}, muxes={imx_list}. Is that block powered and plugged in?")
 
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
    MAX_TRIES = int(parameter_list.get("max_bad_reads", 3))               # attempts per frequency point
 
    # internal state - pre 1st measurement
    gain = 1.0
    inoise = 0.0
    vnoise = 0.0
    ienoise = 0.0
 
    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])
    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
 
    skipped = 0
    try:
        pstat.open()   # explicit open so close() in finally can release it (same pattern as geis.py)
        mux.open()     # exactly once
 
        active_ch = cell - mux_pstat_index * 8
        for ch in range(8):                              # 8 channels on this MUX
            if ch != active_ch:
                mux.set_off_mode(ch, tkp.MUX_CELL_LOCAL) # isolate inactive channels to their local DAC
                mux.set_dac(ch, dc_voltage)              # hold them at a safe potential (your OCV / 0)
        mux.set_cell(active_ch)
 
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
        pstat.set_voltage(dc_voltage)
        pstat.set_cell(tkp.CELL_ON)
        dc_current = pstat.measure_i()
        ac_current = estimated_z * ac_voltage
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
            measured = False
            for attempt in range(1, MAX_TRIES + 1):
                if readz.Measure(freq, ac_voltage, dc_voltage):     # good reading
                    zcurve.add_point(readz)
                    measured = True
                    break
                print(f"Bad value at {freq:.1f} Hz (attempt {attempt}/{MAX_TRIES})")
                time.sleep(0.01)                                    # brief settle before retrying
            if not measured:
                print(f"Skipping {freq:.1f} Hz after {MAX_TRIES} bad attempts.")
                skipped += 1
            step += 1                                              # ALWAYS advance to the next frequency
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
 
    if skipped:
        print(f"PEIS finished -- {skipped} of {max_points} frequency point(s) skipped.")
 
    # Build the DataFrame straight from the acquired curve -- no file round-trip.
    df = pd.DataFrame(zcurve.acq_data())
    if "zimag" in df.columns:
        df["reflected_zimag"] = -df["zimag"]
 
    # optional: keep the temperature + timestamp columns
    try:
        temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
        df["temp(C)"] = temper.get_temperature()[1]
    except Exception:
        pass
    df["datetime"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
 
    return df


if __name__ == "__main__":
   

    parameter_list = { }
    parameter_list['initial_freq']= 2000000.0
    parameter_list['final_freq'] = 2.0
    parameter_list['points_per_decade'] = 40
    parameter_list['estimated_z'] = 2000.0
    parameter_list['dc_voltage'] = 0.0

    zcurve = run_peis(parameter_list)



def initialize_pstat(pstat):
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