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

#Statement of work
#A modular rerunnable experiment according to given parameters. The resulting 
class CP(Experiment): 
    def __init__(self, amperage_list : list, scanrates : list, holdtimes : list, maxcycles : int,sample_period : float, PSTATMODE : tkp.CTRLMODE, **kwargs):
        """This class creates a Cylic voltammatry experiment

        Parameters
        ------------

        amperage_list : list(float)
             List of voltages to be used in the CP [Vinit,V1,V2,Vfinal]

        scanrates : list(float)
            List of scan rates to be used in the CP [Vinit -> V1,V1 -> V2,V2 -> Vfinal]

        holdtimes : list(float) 
            List of hold times to be used in the CP [Apex1, Apex2, Final]

        Sample Period : float 
            Time between data-acquisition steps in seconds

        Max Cycle(int): 
            Number of cycles for the CP

        CtrlMode(Enumeration:CTRLMODE):
             Potentiostat control mode. GSTATMODE or PSTATMODE
        
        **kwargs 
            As of right now Kwargs are the stop at conditions for each curve. The compatible stop ats for CP experiments are:
                "vmax"
                "vmin"
            """

        self.amperage_list = amperage_list
        self.scanrates = scanrates
        self.holdtimes = holdtimes
        self.sample_time = sample_period
        self.maxcycles = maxcycles
        self.PSTATMODE = tkp.GSTATMODE
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
            pstat.set_ctrl_mode(tkp.GSTATMODE) #NOTE This was tkp.PSTATMODE before 4/16/26
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
            pstat.set_ie_range(8)
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
        """This function returns the total number of data points for the CP"""
        SignalPoints0 = int(abs(self.amperage_list[1] - self.amperage_list[0])/(self.sample_time * self.scanrates[0]) + .5)
        SignalPoints1 = int((self.holdtimes[0]/(self.sample_time) ) +0.5)
        SignalPoints2 = int(abs(self.amperage_list[2] - self.amperage_list[1])/(self.sample_time * self.scanrates[0]) + .5)
        SignalPoints3 = int(abs(self.holdtimes[1] / self.sample_time) + 0.5)  # Hold 2
        SignalPoints4 = int(abs((self.amperage_list[3] - self.amperage_list[2]) / (self.sample_time * self.scanrates[0])) + 0.5)  # V2 to Vfinal
        SignalPoints5 = int((self.holdtimes[2] / self.sample_time) + 0.5)  # Hold 3 
        return round(SignalPoints0 + SignalPoints1 + SignalPoints2 + SignalPoints3 + SignalPoints4 + SignalPoints5)
    
    def run_cp_test(self, pstat, max_size = 100000):
        """Runs the triangle wave experiment. A Cyclic voltammagram if in pstatmode, otherwise a galvanodynamic triangle wave
        
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
        max_size = max_size
        
        curve = tkp.CiivCurve(pstat, max_size)
        

                                        #Iinit, Tinit, SamplePeriod,     CtrlMode
        signal = pstat.signal_const_new(0.0005, 10, self.sample_time, tkp.GSTATMODE)
        print(signal)
        #signal = pstat.signal_d_step_new(0.001, 0,     0.1,    10,      1,      0,      self.sample_time, tkp.GSTATMODE)
        pstat.set_signal_const(signal)
        #signal = pstat.signal_r_up_dn_new(self.amperage_list, self.scanrates, self.holdtimes, self.sample_time,self.maxcycles, self.PSTATMODE)
        #pstat.set_signal_r_up_dn(signal)
        #self.set_stop_ats(curve)
        pstat.set_cell(True)
        points = self.estimated_point_count()
        total_time = self.estimated_total_time()
        #v_lims = 1.8
        #curve.set_stop_v_min(True, -1*v_lims)
        #curve.set_stop_v_max(True, v_lims)
        
        tkp.log.info(f"Running CP experiment there will be ~{points} rows of data and the experiment will take {total_time} seconds")
        print(curve)
        curve.run(True)
        t0 = time.time()
        while curve.running():
            #Time.sleep(1)
            
            data = curve.last_data_point()
            
            #print(data)
            #point = data['point']
            #voltage = data['vf']
            #current = data['im']
            #tkp.log.info(f'Point {point + 1} of {points}\nVoltage: {voltage:.14f} voltage\nCurrent: {current:.14f} Amps')
        t1 = time.time()
        #print(t1-t0)
        #print((t1-t0)/99)
        pstat.set_cell(False)
        data = curve.acq_data()
        #print(data)
        if data['stop_test'][-1] != 0:
            tkp.log.info(f'Stop test occurred at point {data["point"]}')
        print("CP completed")
        self.is_run = True
        if self.PSTATMODE == tkp.PSTATMODE:
            self.last_value = data['vf'][-1]
        elif self.PSTATMODE == tkp.GSTATMODE:
            self.last_value = data['im'][-1]
        return data


    def run_cp_test_looping(self, pstat, mux, channels, max_size = 100000):
        """Runs the triangle wave experiment. A Cyclic voltammagram if in pstatmode, otherwise a galvanodynamic triangle wave
        
        Parameters
        ----------
        pstat : tkp.PSTAT
            The potentiostat that will be used to generate the wave form 
        mux: tkp.IMX8
            Pass in a mux
        channels: list
            Pass in a list of the channels you'd like to loop through, like [0,2,4,5]. Limited to 0->7
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
        max_size = max_size
        
        curve = tkp.CiivCurve(pstat, max_size)
        

                                        #Iinit, Tinit, SamplePeriod,     CtrlMode
        signal = pstat.signal_const_new(0.0005, 10, self.sample_time, tkp.GSTATMODE)
        print(signal)
        #signal = pstat.signal_d_step_new(0.001, 0,     0.1,    10,      1,      0,      self.sample_time, tkp.GSTATMODE)
        pstat.set_signal_const(signal)
        #signal = pstat.signal_r_up_dn_new(self.amperage_list, self.scanrates, self.holdtimes, self.sample_time,self.maxcycles, self.PSTATMODE)
        #pstat.set_signal_r_up_dn(signal)
        #self.set_stop_ats(curve)
        pstat.set_cell(True)
        points = self.estimated_point_count()
        total_time = self.estimated_total_time()
        #v_lims = 1.8
        #curve.set_stop_v_min(True, -1*v_lims)
        #curve.set_stop_v_max(True, v_lims)
        
        tkp.log.info(f"Running CP experiment there will be ~{points} rows of data and the experiment will take {total_time} seconds")
        print(curve)
        curve.run(True)
        t0 = time.time()
        loop_counter = 0

        cell_cp_data = [[] for i in range(len(channels))]

        while curve.running():
            #Time.sleep(1)
            
            data = curve.last_data_point()
            index = loop_counter%len(channels)
            cell_cp_data[index].append(data)
            mux.set_cell(channels[loop_counter%len(channels)])
            loop_counter += 1
            #print(data)
            #point = data['point']
            #voltage = data['vf']
            #current = data['im']
            #tkp.log.info(f'Point {point + 1} of {points}\nVoltage: {voltage:.14f} voltage\nCurrent: {current:.14f} Amps')
        t1 = time.time()
        print(t1-t0)
        print((t1-t0)/99)
        pstat.set_cell(False)
        data = curve.acq_data()
        print(data)
        if data['stop_test'][-1] != 0:
            tkp.log.info(f'Stop test occurred at point {data["point"]}')
        print("CP completed")
        self.is_run = True
        if self.PSTATMODE == tkp.PSTATMODE:
            self.last_value = data['vf'][-1]
        elif self.PSTATMODE == tkp.GSTATMODE:
            self.last_value = data['im'][-1]
        return cell_cp_data



    def initialize_pstat(self,pstat):
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
            pstat.set_ie_range(8)
            pstat.set_pos_feed_enable(False)
            pstat.set_analog_out(0.0)
            pstat.set_voltage(0.0)
            pstat.set_pos_feed_resistance(0.0)
        else:
            self.dc_105_initialize_pstat(pstat, self.sample_time)
            #pstat.set_ctrl_mode(tkp.GSTATMODE) #previously set_PSTATMODE
            #pstat.set_ie_stability(tkp.STABILITY_FAST) #previously set_stability
            #pstat.set_vch_range(10.0)
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

def example_cp_test(cell):
    tkp.toolkitpy_init('chrono.py') 

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

    #TODO update so that only a cell number goes in, and the pstat index and imx index are calculated from that

    mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])

    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
    mux.open()

    mux.set_cell(cell-mux_pstat_index*8)

    active_cells = [0] * 8
    # An array initially stating that we don't want to use any of the mux cells
    active_cells[0] = True
    active_cells[1] = True
    #We will use channel one only

    try:
        sample_time = 0.1
        signal = pstat.signal_d_step_new(0.001, 0, 0.5, 1, 1, 1, sample_time, tkp.GSTATMODE)
        pstat.set_ctrl_mode(tkp.GSTATMODE)

        for i in range(len(active_cells)):
            if active_cells[i]:
                print(f"-----Starting channel {i}-----")
                pstat.set_signal_d_step(signal)
                curve = tkp.CiivCurve(pstat, 1000)
                mux.set_off_mode(i, tkp.MUX_CELL_OPEN)
                mux.set_cell(i)
                pstat.set_cell(True)
                curve.run(True) 
                while curve.running():
                    Time.sleep(sample_time)
                    data = curve.last_data_point()
                    point = data['point']
                    voltage = data['vf']
                    current = data['im']
                    time = data['time']
                    print(f"Point {point}\nTime {time}s\n voltage: {voltage}V\nCurrent: {current}A\n")
                pstat.set_cell(False)
                mux.set_cell(False) #Sets all cells to inactive
    finally:
        del pstat
        del mux
        Time.sleep(1)



def run_cp_output(output_file_name,values = [[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1], electrode_used = "Pt", save_to_db_folder = True, standard = False):
    
    tkp.toolkitpy_init("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    cp = CP(values[0],values[1],values[2],values[3],values[4], tkp.GSTATMODE, imax = 10)
    data = cp.run_cp_test(pstat, max_size = 100000)
    #TODO  
    #add the new columns to the actual CSV file

    if standard:
        out_path = "res/standard/cp/" + output_file_name+ ".csv"
    else:
        out_path = "res/cp/" + output_file_name + ".csv"
    np.savetxt(out_path, data, delimiter = ',', header = 'Point,time,Vf,Vu,Im,Ach,vsig,temp,Cycle,ie_range,overload,stop_test', fmt = '%s') 
    print("getting temp")
    temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
    temperature = temper.get_temperature()[1]
    
    df = pd.read_csv(out_path, index_col='# Point')
    df['temp(C)'] = temperature
    df.to_csv(out_path)

    if save_to_db_folder and not standard:
        #C:\AttomRobotFiles\Data\DB_Missaka\eis
        db_path = Path(r"C:\AttomRobotFiles\Data\DB_Missaka\cp") / f"{output_file_name}.csv"
        df.to_csv(db_path)   

    if standard:
        s_df_file = "res/standard/std_cp_test_summaries.csv"
    else:
        s_df_file = "res/cp_test_summaries.csv"

    s_df = pd.read_csv(s_df_file)

    s = time.localtime(time.time())
    curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)

    vf_diff,vf_max,vf_min  = cp_interpret(out_path)
    # overP, i0, alpha_c = kinetic_fit(out_path)
    new_row = pd.DataFrame([[output_file_name, vf_max, vf_min, vf_diff, None, None, None, temperature, curr_time]], columns=['test name', 'vf_max', 'vf_min', 'vf_diff',  "overP", "i0", "alpha_c", 'temp', 'time'])
    s_df = pd.concat([s_df, new_row], ignore_index=True)
    s_df.to_csv(s_df_file, index=False)   

    if save_to_db_folder and not standard:
        return db_path


def run_cp_cell(cell, current=0, time_run=10, output_file_name = "chronopotentiometry", electrode_used = "Pt", path_to_save_to = r"C:\AttomRobotFiles\Data\DB_Missaka\cp", save_to_db_folder = True, standard = False):
    values = [[0, current, current, 0], [0.1, 0.1, 0.1], [time_run/2, time_run/2, 0.05], 1, 0.1]
    """
    #Vinit, Tinit, Vstep1, Tstep1, Vstep2, Tstep2, SamplePeriod,     CtrlMode
    values:
        amperage_list : list(float)
             List of amperages to be used in the CP [Iinit,I1,I2,Ifinal]

        scanrates : list(float)
            List of scan rates to be used in the CP [Iinit -> I1,I1 -> I2,I2 -> Ifinal]

        holdtimes : list(float) 
            List of hold times to be used in the CP [Apex1, Apex2, Final]
    """
    tkp.toolkitpy_init("open_circuit_voltage.py")
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
            print(f"!!!!! Found a non IMX or IFC type device. It is called: {device_name}")

    #TODO update so that only a cell number goes in, and the pstat index and imx index are calculated from that

    mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])

    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
    mux.open()

    mux.set_cell(cell-mux_pstat_index*8)

    cp = CP(values[0],values[1],values[2],values[3],values[4], tkp.GSTATMODE, imax = 50)
    data = cp.run_cp_test(pstat, max_size = 100000)
    #TODO  
    #add the new columns to the actual CSV file

    if standard:
        out_path = "res/standard/cp/" + output_file_name+ ".csv"
    else:
        out_path = "res/cp/" + output_file_name + ".csv"
    np.savetxt(out_path, data, delimiter = ',', header = 'Point,time,Vf,Vu,Im,Ach,vsig,temp,Cycle,ie_range,overload,stop_test', fmt = '%s') 
    print("getting temp")
    temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
    temperature = temper.get_temperature()[1]
    
    df = pd.read_csv(out_path, index_col='# Point')
    df['temp(C)'] = temperature
    df.to_csv(out_path)

    if save_to_db_folder and not standard:
        #C:\AttomRobotFiles\Data\DB_Missaka\eis
        db_path = Path(path_to_save_to) / f"{output_file_name}.csv"
        df.to_csv(db_path)   

    if standard:
        s_df_file = "res/standard/std_cp_test_summaries.csv"
    else:
        s_df_file = "res/cp_test_summaries.csv"

    s_df = pd.read_csv(s_df_file)

    s = time.localtime(time.time())
    curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)

    vf_diff,vf_max,vf_min  = cp_interpret(out_path)
    # overP, i0, alpha_c = kinetic_fit(out_path)
    new_row = pd.DataFrame([[output_file_name, vf_max, vf_min, vf_diff, None, None, None, temperature, curr_time]], columns=['test name', 'vf_max', 'vf_min', 'vf_diff',  "overP", "i0", "alpha_c", 'temp', 'time'])
    s_df = pd.concat([s_df, new_row], ignore_index=True)
    s_df.to_csv(s_df_file, index=False)

    if save_to_db_folder and not standard:
        return db_path


def run_cp_cell_looping(cells, current=0, time_run=10, output_file_name = "chronopotentiometry", electrode_used = "Pt", path_to_save_to = r"C:\AttomRobotFiles\Data\DB_Missaka\cp", save_to_db_folder = True, standard = False):
    values = [[0, current, current, 0], [0.1, 0.1, 0.1], [time_run/2, time_run/2, 0.05], 1, 0.1]
    """
    #Vinit, Tinit, Vstep1, Tstep1, Vstep2, Tstep2, SamplePeriod,     CtrlMode
    values:
        amperage_list : list(float)
             List of amperages to be used in the CP [Iinit,I1,I2,Ifinal]

        scanrates : list(float)
            List of scan rates to be used in the CP [Iinit -> I1,I1 -> I2,I2 -> Ifinal]

        holdtimes : list(float) 
            List of hold times to be used in the CP [Apex1, Apex2, Final]
    """
    tkp.toolkitpy_init("open_circuit_voltage.py")
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
            print(f"!!!!! Found a non IMX or IFC type device. It is called: {device_name}")

    #TODO update so that only a cell number goes in, and the pstat index and imx index are calculated from that

    mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])

    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
    mux.open()

    mux.set_cell(cell-mux_pstat_index*8)

    cp = CP(values[0],values[1],values[2],values[3],values[4], tkp.GSTATMODE, imax = 50)
    data = cp.run_cp_test(pstat, max_size = 100000)
    #TODO  
    #add the new columns to the actual CSV file

    if standard:
        out_path = "res/standard/cp/" + output_file_name+ ".csv"
    else:
        out_path = "res/cp/" + output_file_name + ".csv"
    np.savetxt(out_path, data, delimiter = ',', header = 'Point,time,Vf,Vu,Im,Ach,vsig,temp,Cycle,ie_range,overload,stop_test', fmt = '%s') 
    print("getting temp")
    temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
    temperature = temper.get_temperature()[1]
    
    df = pd.read_csv(out_path, index_col='# Point')
    df['temp(C)'] = temperature
    df.to_csv(out_path)

    if save_to_db_folder and not standard:
        #C:\AttomRobotFiles\Data\DB_Missaka\eis
        db_path = Path(path_to_save_to) / f"{output_file_name}.csv"
        df.to_csv(db_path)   

    if standard:
        s_df_file = "res/standard/std_cp_test_summaries.csv"
    else:
        s_df_file = "res/cp_test_summaries.csv"

    s_df = pd.read_csv(s_df_file)

    s = time.localtime(time.time())
    curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)

    vf_diff,vf_max,vf_min  = cp_interpret(out_path)
    # overP, i0, alpha_c = kinetic_fit(out_path)
    new_row = pd.DataFrame([[output_file_name, vf_max, vf_min, vf_diff, None, None, None, temperature, curr_time]], columns=['test name', 'vf_max', 'vf_min', 'vf_diff',  "overP", "i0", "alpha_c", 'temp', 'time'])
    s_df = pd.concat([s_df, new_row], ignore_index=True)
    s_df.to_csv(s_df_file, index=False)

    if save_to_db_folder and not standard:
        return db_path



def cp_interpret(filename):
    df_file = filename
    df = pd.read_csv(df_file, index_col='# Point')

    positive,zero,negative = find_peaks_and_zero_crossings(df)

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

    vf_diff = vf_max-vf_min

    return(vf_diff,vf_max,vf_min )

'''
if __name__ == "__main__":
    tkp.toolkitpy_init("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    cv = CV([0, 1, -1, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1, tkp.PSTATMODE, imax = 10)
    data = cv.run(pstat)
    np.savetxt("test.csv", data, delimiter = ',', header = 'Point, time, Vf, Vu, Im, Ach, vsig, temp, Cycle, ie_range, overload, stop_test', fmt = '%s')
'''