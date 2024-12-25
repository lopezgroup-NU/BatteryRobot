import pandas as pd
from temper_windows import TemperWindows
import time

'''
# from GamryUtils import PStat

# class CV(PStat):
#     def __init__(self, pstat):
#     """This function changes the configuration of your pstat Inputs
#     -------------------------------------------------------------
#     pstat: Pypstat object
#         The pstat that you want to change the parameters of
# 
#     """
#     #These will be some of the Framework parameters
#         pstat.set_ach_select(tkp.ACHSELECT_GND)
#         pstat.set_ie_stability(tkp.STABILITY_NORM)
#         pstat.set_ca_speed(tkp.CASPEED_NORM)
#         pstat.set_ground(tkp.FLOAT)
#         pstat.set_ich_range(3.0)
#         pstat.set_ich_range_mode(False)
#         pstat.set_ich_offset_enable(False)
#         pstat.set_vch_range(10.0)
#         pstat.set_vch_range_mode(True)
#         pstat.set_vch_offset_enable(False)
#         pstat.set_ach_range(3.0)
#         pstat.set_ie_range_lower_limit(0) #For none
#         pstat.set_pos_feed_enable(False)
#         pstat.set_analog_out(0.0)
#         pstat.set_voltage(0.0)
#         pstat.set_pos_feed_resistance(0.0)
#         self.pstat = pstat
#     
#     def plot_cv(curve, data, ScanRate, ScanRates, ScanNumber, ScanDelay, data_frame, fig, ax,colors):
#         plt.cla()
#         ax.set_xlabel('E vs Eref (V)')
#         ax.set_ylabel('Current (A)')
#         ax.scatter(data['vf'][1:], data['im'][1:], marker = '.', label = ScanRate,color = colors[ScanNumber])
#         plt.legend(loc = 'upper left')
#         plt.legend(title = "Scan Rate (V/s)")
#         for i in range(ScanNumber):
#                 ax.scatter(data_frame[i]['vf'], data_frame[i]['im'], marker = '.', label = ScanRates[i], color = colors[i])
#                 plt.legend(loc = 'upper left')
#                 plt.legend(title = "Scan Rate (V/s)")
#         plt.tight_layout()
#         plt.pause(0.02)
#         
#     """A little bit of explanation on the r_up_dn_new 
#     Parameter 1: Vertex: List[float] 
#         Four-element array that specifies the inital, Apex1, Apex2, and final value in volts or amperes
#     Parameter2: VectorScanRate: List[float]
#         Three-element arrayt that specifies the inital (to apex1),apex2, and final scan rates in volts/seconds or ampere seconds
#     Parameter3: VectorHoldTime: list[float]
#         Three-element array that specifies the hold times in seconds at Apex1, Apex2, and at the end.
#     Parameter 4: SampleRate: Float
#         Time between data acquisition steps
#     Parameter 5: MaxCycles: int
#         Maximum number of applied cycles
#     Parameter 6: CtrlMode: CTRLMODE <- Enumerator
#         The potentiostats control mode
#     """

def initialize_pstat(pstat):
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
    pstat.set_pos_feed_enable(False)
    pstat.set_analog_out(0.0)
    pstat.set_voltage(0.0)
    pstat.set_pos_feed_resistance(0.0)

    
def plot_cv(curve, data, ScanRate, ScanRates, ScanNumber, ScanDelay, data_frame, fig, ax,colors):
    plt.cla()
    ax.set_xlabel('E vs Eref (V)')
    ax.set_ylabel('Current (A)')
    ax.scatter(data['vf'][1:], data['im'][1:], marker = '.', label = ScanRate,color = colors[ScanNumber])
    plt.legend(loc = 'upper left')
    plt.legend(title = "Scan Rate (V/s)")
    for i in range(ScanNumber):
            ax.scatter(data_frame[i]['vf'], data_frame[i]['im'], marker = '.', label = ScanRates[i], color = colors[i])
            plt.legend(loc = 'upper left')
            plt.legend(title = "Scan Rate (V/s)")
    plt.tight_layout()
    plt.pause(0.02)
        

def run_cv(
    file_name, #Parent file name. Output data files will be named "file_name with x scan rate.csv"
    plot = False,
    VInit = .25, #Initial Voltage
    VLimit1 = .5, #Potentiostat scans to Voltage Apex 1
    V1hold = 0.0, #Hold time for first vertex (s)
    VLimit2 = .25, #Potentiostat scans to Voltage Apex 2
    V2hold = 0.0, #Hold time for second vertex (s)
    VFinal = 0.5, #Final Voltage
    Vfhold = 0.0, #Hold time for the final vertex (s)
    ScanRate = 0.1, #Scan rate (V/s)
    ResVal  = 0.001, #Step Size (V)
    Cycles = 1, #Number of cycles per scan
    NumOfScans = 10,   #Total number of scans collected sequentially
    Increment = 0.01, #Between each scan from NumOfScans, the ScanRate will change by Increment (V/s)
    ScanDelay = 0,    #Time delay between each subsequent scan. (s)
    SampleMode = 1):
    
    NumOfScans = 10
    number_of_colors = NumOfScans
    cmap = plt.get_cmap("tab20b") # Choose a color scheme that you think looks best. Or whatever system of coloring the scans
    colors = [cmap(i) for i in np.linspace(0, 1, number_of_colors)]

    tkp.toolkitpy_init("RunPyBind")
    pstat = tkp.Pstat("PSTAT") 
    initialize_pstat(pstat)
    SampleTime  = ResVal/ScanRate
    ScanRates = []
    data_frame = dict()
    fig = plt.figure()
    ax = fig.gca()
    curve.set_stop_i_min(True, -.01)  #new
    curve.setstopimax(True, .01)   #new
    
    for ScanNumber in range(NumOfScans):
        estimated_time = (int(abs(VLimit1 - VInit) / ResVal + 0.5) + int(abs(V1hold/SampleTime)+0.5) + Cycles*(int(abs((VLimit2 - VLimit1) / ResVal) + 0.5) + int((V2hold / SampleTime) + 0.5)) + int(abs((VFinal - VLimit2) / ResVal) + 0.5) + int((Vfhold / SampleTime) + 0.5))*SampleTime
        print("This scan should take {} seconds with a {} second delay between cycles".format(int(estimated_time +.5), ScanDelay)) #This is just so you know that your loop is or is not infinite
        Signal = pstat.signal_r_up_dn_new([VInit, VLimit1, VLimit2, VFinal], [ScanRate, ScanRate, ScanRate], 
                                        [V1hold,V2hold,Vfhold],SampleTime,Cycles,SampleMode)
        pstat.set_signal_r_up_dn(Signal)
        pstat.init_signal()
        pstat.set_cell(True)
        MaxSize = 100000
        CV = tkp.RCVWrapper(pstat,MaxSize)
        CV.run(True)
        fileName = file_name + ' with ' +str(ScanRate) + ' scan rate.csv'
        while CV.running():
            time.sleep(0.010)
            data = CV.acq_data()
            np.savetxt(fileName, data, delimiter = '\t', header = 'IERange, Overload, Time, Vsig, Ach, Im, Vf, Vu, Cycle, Temp, StopTest', fmt='%s')
            # if plot:                
            #     plotCV(CV, data, ScanRate,ScanRates, ScanNumber, ScanDelay, data_frame,fig, ax,colors)
            
        data_frame[ScanNumber] = data #data is added to the dictionary
        ScanRates.append(ScanRate) #the ScanRate used for data collection is added to a list
        ScanRate = ScanRate + Increment
        SampleTime  = ResVal/ScanRate 
        pstat.set_cell (True) #cell is turned off to prepare for the next interation of the loop
        time.sleep(ScanDelay) #Scan delay between CV interations as determined by user parameter input
        print("One loop done") #Another print so that you know you are moving along in your code
    print("All done")   

if __name__ == "__main__":
    run_cv("cv")
'''    
import toolkitpy as tkp
import time as Time
import numpy as np
from .experiment import Experiment
#Statement of work
#A modular rerunnable experiment according to given parameters. The resulting 
class CV(Experiment): 
    def __init__(self, voltage_list : list, scanrates : list, holdtimes : list, maxcycles : int,sample_period : float, PSTATMODE : tkp.CTRLMODE, **kwargs):
        """This class creates a Cylic voltammatry experiment

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
        super().__init__(kwargs)
        print(kwargs)
        
    def dc_105_initialize_pstat(pstat, sampling_rate):
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
        """This function returns the total number of data points for the CV"""
        SignalPoints0 = int(abs(self.voltage_list[1] - self.voltage_list[0])/(self.sample_time * self.scanrates[0]) + .5)
        SignalPoints1 = int((self.holdtimes[0]/(self.sample_time) ) +0.5)
        SignalPoints2 = int(abs(self.voltage_list[2] - self.voltage_list[1])/(self.sample_time * self.scanrates[0]) + .5)
        SignalPoints3 = int(abs(self.holdtimes[1] / self.sample_time) + 0.5)  # Hold 2
        SignalPoints4 = int(abs((self.voltage_list[3] - self.voltage_list[2]) / (self.sample_time * self.scanrates[0])) + 0.5)  # V2 to Vfinal
        SignalPoints5 = int((self.holdtimes[2] / self.sample_time) + 0.5)  # Hold 3 
        return round(SignalPoints0 + SignalPoints1 + SignalPoints2 + SignalPoints3 + SignalPoints4 + SignalPoints5)
    
    def run_cv(self, pstat, max_size = 100000):
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
        curve = tkp.RcvCurve(pstat, max_size)
        
        self.filter_stop_ats(curve, self.PSTATMODE)
        self.set_stop_ats(curve)
        signal = pstat.signal_r_up_dn_new(self.voltage_list, self.scanrates, self.holdtimes, self.sample_time,self.maxcycles, self.PSTATMODE)
        pstat.set_signal_r_up_dn(signal)
        self.set_stop_ats(curve)
        pstat.set_cell(True)
        points = self.estimated_point_count()
        total_time = self.estimated_total_time()
        curve.set_stop_i_min(True, -.000025)  #new
        curve.set_stop_i_max(True, .000025)   #new
        
        tkp.log.info(f"Running CV experiment there will be ~{points} rows of data and the experiment will take {total_time} seconds")
        curve.run(True)
        while curve.running():
            Time.sleep(1)
            data = curve.last_data_point()
            point = data['point']
            voltage = data['vf']
            current = data['im']
            tkp.log.info(f'Point {point + 1} of {points}\nVoltage: {voltage:.4f} voltage\nCurrent: {current:.4f} Amps')
        
        pstat.set_cell(False)
        data = curve.acq_data()
        if data['stop_test'][-1] != 0:
            tkp.log.info(f'Stop test occurred at point {data["point"]}')
        print("Cyclic Voltammatry completed")
        self.is_run = True
        if self.PSTATMODE == tkp.PSTATMODE:
            self.last_value = data['vf'][-1]
        elif self.PSTATMODE == tkp.GSTATMODE:
            self.last_value = data['im'][-1]
        return data
    
        
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
            pstat.set_PSTATMODE(tkp.GSTATMODE)
            pstat.set_stability(tkp.STABILITY_FAST)
            pstat.set_vch_range(10.0)
        return  

def run_cv2(output_file_name,values = [[0, 2, -2, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1]):
    tkp.toolkitpy_init("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    cv = CV(values[0],values[1],values[2],values[3],values[4], tkp.PSTATMODE, imax = 10)
    data = cv.run_cv(pstat, max_size = 100000)
    np.savetxt("res/cv/" + output_file_name + ".csv", data, delimiter = ',', header = 'Point,time,Vf,Vu,Im,Ach,vsig,temp,Cycle,ie_range,overload,stop_test', fmt = '%s') 


    df_file = "res/" + output_file_name+ ".csv"
    s_df_file = "res/cv_test_summaries.csv"
    df = pd.read_csv(df_file, index_col='# Point')
    s_df = pd.read_csv(s_df_file)

    temper = TemperWindows(vendor_id=0x3553, product_id=0xa001)
    temperature = temper.get_temperature()[1]
    s = time.localtime(time.time())
    curr_time = time.strftime("%Y-%m-%d %H:%M:%S", s)

    targ_max = 0.000024
    targ_min = -0.000024

    im_col = df["Im"]

    #get xmax
    #translate column by target and get absolute values. find index of minimum (closest to 0)
    im_col_translated = (im_col - targ_max).abs()
    min_idx = im_col_translated.idxmin()
    vf_max = df['Vf'].loc[min_idx]  # Use .loc to get the value at that index

    #get xmin
    im_col_translated = (im_col - targ_min).abs()
    min_idx = im_col_translated.idxmin()
    vf_min = df['Vf'].loc[min_idx]  # Use .loc to get the value at that index

    vf_diff = vf_max-vf_min

    new_row = pd.DataFrame([["2M_cv0", vf_max, vf_min, vf_diff, temperature, curr_time]], columns=['test name', 'vf_max', 'vf_min', 'vf_diff', 'temp', 'time'])
    s_df = pd.concat([s_df, new_row], ignore_index=True)
    s_df.to_csv(s_df_file, index=False)   

'''
if __name__ == "__main__":
    tkp.toolkitpy_init("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    cv = CV([0, 1, -1, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1, tkp.PSTATMODE, imax = 10)
    data = cv.run(pstat)
    np.savetxt("test.csv", data, delimiter = ',', header = 'Point, time, Vf, Vu, Im, Ach, vsig, temp, Cycle, ie_range, overload, stop_test', fmt = '%s')
'''