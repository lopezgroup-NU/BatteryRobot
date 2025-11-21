import sys
import winreg
import toolkitpy as tkp
import numpy as np                       #Used to store and manipulate raw data output
import time as tm                          #Used for script time delay
import math
import os
import matplotlib
from matplotlib import pyplot as plt
import matplotlib.animation as animation
import pandas as pd
from pathlib import Path
matplotlib.use('qtagg')


def initialize_pstat(pstat):
    """This function sets the configuration of your pstat
    """
    #These will be some of the Framework parameters
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
    pstat.set_ie_range(8)
    pstat.set_pos_feed_enable(False)
    pstat.set_analog_out(0.0)
    pstat.set_voltage(0.0)
    pstat.set_pos_feed_resistance(0.0)


def ca(parameter_list, graph, catalyst="unknown", save_dest= "ca.jpg"):
    ca_data_is_saved = False
    initial_voltage = parameter_list.get("initial_voltage", 0.0)
    step1_voltage = parameter_list.get("step1_voltage",0.1)
    step2_voltage = parameter_list.get("step2_voltage", 0.2)
    initial_time = parameter_list.get("initial_time", 1.0)
    step1_time = parameter_list.get("step1_time", 5.0)
    step2_time = parameter_list.get("step2_time", 5.0)
    sample_time = parameter_list.get("sample_time", 0.005)   
    tkp.toolkitpy_init("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    pstat.set_ctrl_mode(tkp.PSTATMODE)
    chronoa_curve = tkp.ChronoACurve(pstat, 10000)

    SampleMode = 1 #Noise Reject
    initialize_pstat(pstat)
    signal = pstat.signal_d_step_new(initial_voltage, initial_time, step1_voltage, step1_time, step2_voltage, step2_time, sample_time, tkp.PSTATMODE) 
    pstat.set_signal_d_step(signal)  # double step chronoamp
    pstat.init_signal()            # preinitialize signal so there is not a startup glitch
    pstat.set_cell(True)
    tm.sleep(0.010)
    total_frames = (initial_time + step1_time + step2_time)/sample_time
    if graph:
        fig = plt.figure()
        ax = fig.gca()
        plt.cla()
        scatter = ax.scatter([],[], c = "b", s = 5)
        plt.title("Chronoamperometery")
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Current (A)')
    chronoa_curve.run(True)
    
    
    def update(Frame):
        if len(chronoa_curve.acq_data()['time']) < 1:
            fig.canvas.draw()
            fig.canvas.flush_events()
        else:
            data = chronoa_curve.acq_data()
            time = data['time'][:]
            current = data['im'][:]
            ca_data = np.stack([time, current]).T
            ax.set_xlim(time.min()- abs(time.min())*.2, time.max()+ abs(time.max())*.2)
            ax.set_ylim(current.min() - abs(current.min())*.2, current.max() + abs(current.max())*.2)
            scatter.set_offsets(ca_data)
        if not chronoa_curve.running():
            ax.set_title("Finished running \nClose window to exit code")
        if len(chronoa_curve.acq_data()['time']) == total_frames-1:
            print("finished getting data")
            print(ca_data)
        # if len(ca_data) == total_frames and not ca_data_is_saved:
        #     print("finished getting data")
            
        #     print(ca_data)
        #     df = pd.DataFrame(ca_data, columns=['time(sec)', 'im(A)'])
        #     output_file_name = "ca_timeIs_" + f"{tm.time()}" + "_catalystIs" + f"{catalyst}"
        #     #TODO: 
        #     """We need to create a branching system for the DB which is able to save the ca data files 
        #     into different bins depending on the catalyst which was used. Ciara said that she'll check w/
        #     collaborators to see exactly what those bins should be, but for now we will just save all into ../ca"""
        #     db_path = Path(r"c:\Users\llf1362\Desktop\DB\ca") / f"{output_file_name}.csv"
        #     df.to_csv(db_path)
        #     ca_data_is_saved = True

    
    if graph: 
        ani = animation.FuncAnimation(fig = fig, func = update, frames = int(total_frames), interval = sample_time)
        while chronoa_curve.running():
            plt.show(block = False)
            plt.pause(.5)
        tm.sleep(1)
        # plt.close()
    else: 
        while chronoa_curve.running():
            data = chronoa_curve.acq_data()
    ca_data = chronoa_curve.acq_data()
    # print(ca_data)
    # df = pd.DataFrame(ca_data, columns=['time(sec)', 'im(A)'])
    # output_file_name = "ca_timeIs_" + f"{tm.time()}" + "_catalystIs" + f"{catalyst}"
    #     #     #TODO: 
    #     #     """We need to create a branching system for the DB which is able to save the ca data files 
    #     #     into different bins depending on the catalyst which was used. Ciara said that she'll check w/
    #     #     collaborators to see exactly what those bins should be, but for now we will just save all into ../ca"""
    # db_path = Path(r"c:\Users\llf1362\Desktop\DB\ca") / f"{output_file_name}.csv"
    # df.to_csv(db_path)   
    if len(ca_data) == total_frames and not ca_data_is_saved:
            print("finished getting data")
            
            print(ca_data)
            df_no_units = pd.DataFrame(ca_data, columns=['time', 'im'])
            df = df_no_units.rename(columns={"time":"time(sec)", "im":"im(A)"})
            output_file_name = "ca_timeIs_" + f"{tm.time()}" + "_catalystIs_" + f"{catalyst}" + "_voltageIs_" + f"{step1_voltage}"
            #TODO: 
            """We need to create a branching system for the DB which is able to save the ca data files 
            into different bins depending on the catalyst which was used. Ciara said that she'll check w/
            collaborators to see exactly what those bins should be, but for now we will just save all into ../ca"""
            db_path = Path(r"c:\Users\llf1362\Desktop\DB\ca") / f"{output_file_name}.csv"
            df.to_csv(db_path)
            ca_data_is_saved = True



    
    pstat.set_cell(False)
    fig.savefig(save_dest, dpi=300)
    del signal 
    return chronoa_curve

# if __name__ == "__main__":

#     tkp.toolkitpy_init("Chronoamperometry.py")
#     pstat = tkp.Pstat("PSTAT")


#     parameter_list = {"initial_voltage": 0.0, "step1_voltage": 0.01,"step2_voltage": 0.02 }
#     curve = chronoamperometry(pstat, parameter_list,True)
#     file_name = "Chronoamperometry.csv"
#     datadir = tkp.default_output_dir()
#     file_name = os.path.join(datadir,file_name)
#     np.savetxt(file_name, curve.acq_data(), delimiter = ',', header ='Time (s), Vf (V), Vu, Im (amp), Ach, Vsig (V), Temp, IERange, Overload', fmt = '%s')
#     print("Done")
#     plt.show()
#     del curve
#     del pstat
#     tkp.toolkitpy_close()
