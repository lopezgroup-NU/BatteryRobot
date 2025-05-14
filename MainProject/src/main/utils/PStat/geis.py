#Galv EIS
from temper_windows import TemperWindows
import toolkitpy as tkp
import numpy as np                       #Used to store and manipulate raw data output
import time                              #Used for script time delay
import math
import matplotlib
import pandas as pd
from utils.DBUtils import MongoQuery
from pathlib import Path

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
    result = factor + rounded
    return result

def initialize_pstat1(pstat):
     #These settings 494 Galvanostatic EIS in the explain scripts. 
     pstat.set_cell(False)          
     pstat.set_ach_select(tkp.ACHSELECT_GND)
     pstat.set_ie_stability(tkp.STABILITY_FAST)
     pstat.set_ca_speed(tkp.CASPEED_NORM)
     pstat.set_ground(tkp.FLOAT)
     pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
     pstat.set_ich_range(3.0)
     pstat.set_ich_range_mode(False)
     pstat.set_ich_filter(2.0)
     pstat.set_vch_range(3.0)
     pstat.set_ich_range_mode(False)
     pstat.set_vch_range_mode(False)
     pstat.set_ich_offset_enable(True)
     pstat.set_vch_offset_enable(True)
     pstat.set_vch_filter(2.50)
     pstat.set_ach_range(3.0)
     pstat.set_ie_range(8)
     pstat.set_ie_range_mode(False)
     pstat.set_ie_range_lower_limit(0)
     pstat.set_analog_out(0.0)
     pstat.set_pos_feed_enable(False)
     pstat.set_irupt_mode(tkp.IRUPTOFF)

def run_geis(output_file_name = "galvanostatic_eis", parameter_list = {}, save_to_db_folder = True):
    tkp.toolkitpy_init("galvanostatic_eis.py")
    pstat = tkp.Pstat("PSTAT")
    #Parameters
    #------------------------------------------------------------------
    initial_freq = parameter_list.get("initial_freq", 250000)
    final_freq = parameter_list.get("final_freq", 1)
    ac_current = parameter_list.get("ac_current", 0.00001) 
    dc_current = parameter_list.get("dc_current", 0.00)
    estimated_z = parameter_list.get("estimated_z", 1000)
    points_per_decade = parameter_list.get("points_per_decade", 10)

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
        print("Initial frequency exceeds upper frequency limit")
        initial_freq = freq_lim_upper
    if(final_freq > freq_lim_upper):
        final_freq = freq_lim_upper
        print("Final frequency exceeds upper frequency limit")
    if(initial_freq < freq_lim_lower):
        initial_freq = freq_lim_lower
        print("Initial frequency exceeds lower frequency limit")
    if(final_freq < freq_lim_lower):
        final_freq = freq_lim_lower
        print("Final frequency exceeds lower frequency limit")
    
    #==========================================
    initialize_pstat1(pstat)
    pstat.set_ctrl_mode(tkp.GSTATMODE)
    pstat.set_i_convention(tkp.ICONVENTION.ANODIC)
    ie_range = pstat.test_ie_range(abs(dc_current) + 1.414*abs(ac_current))
    pstat.set_ie_range(ie_range)
    r_measure = pstat.ie_resistor(ie_range)
    Sdc = r_measure * dc_current
    Sac = r_measure * ac_current
    pstat.set_voltage(Sdc)
    pstat.set_cell(tkp.CELL_ON)
    dc_voltage = pstat.measure_v()

    readz = tkp.ReadZ(pstat)
    readz.set_gain(gain)
    readz.set_inoise(inoise)
    readz.set_vnoise(vnoise)
    readz.set_ienoise(ienoise)
    readz.set_zmod(estimated_z)
    readz.set_idc(dc_current)
    readz.set_speed(1) #Normal
    readz.set_drift_cor(False)
    
    #==========================================
    log_increment = 1.0/points_per_decade
    if initial_freq > final_freq:
        log_increment = -log_increment
    max_points = check_eis_points(initial_freq, final_freq, points_per_decade)
    zcurve = tkp.ZCurve(int(max_points)) #convert max_points to int to prevent error

    current_points = 0
    while current_points < max_points:
        freq = math.pow(10.0, math.log10(initial_freq) + current_points * log_increment)
        status = readz.Measure(freq, ac_current,dc_current)
        if status == False:
            print('Bad Value')
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
        current_points +=1

        time.sleep(.010)

    pstat.set_cell(False)
    out_path = "res/geis/" + output_file_name+ ".csv"
    np.savetxt(out_path, zcurve.acq_data(),delimiter = ',', 
               header = 'point,freq,zreal,zimag,zmod,zphz,zsig,Idc,Vdc,ie_range,gain,vmod,vphz,vsig,vthd,imod,iphz,isig,ithd,zreal_drift,zimag_drift,zmod_drift,zphz_drift')
    
    temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
    temperature = temper.get_temperature()[1]
    

    df = pd.read_csv(out_path, index_col='# point')
    reflected_zimag = [-val for val in df['zimag']]
    df.insert(2, 'reflected_zimag', reflected_zimag)
    df['temp(C)'] = temperature
    df.to_csv(out_path)

    if save_to_db_folder:
        db_path = Path(r"c:\Users\llf1362\Desktop\DB\eis") / f"{output_file_name}.csv"
        df.to_csv(db_path) 

    # extract minima
    s_df_file = "res/geis_test_summaries.csv"
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

    return zcurve

if __name__ == "__main__":
    parameter_list = {}
    parameter_list['initial_freq']= 250000
    parameter_list['final_freq'] = 1.0    
    zcurve = run_geis(parameter_list)
    
    

    
