import os

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

try:
    from .pstat import ensure_toolkit_init
except ImportError:
    _TKP_READY = [False]

    def ensure_toolkit_init(tag="ca.py"):
        if not _TKP_READY[0]:
            tkp.toolkitpy_init(tag)
            _TKP_READY[0] = True

LIVE_HOOK = None

#Statement of work
#A modular rerunnable experiment according to given parameters. The resulting 
class CA(Experiment): 
    def __init__(self, voltage, scanrates : list, holdtime, maxcycles : int, sample_period : float, PSTATMODE : tkp.CTRLMODE, **kwargs):
        """This class creates a Chronoamperometry experiment

        Parameters
        ------------

        Voltage : int or float
            The voltage to hold during the chronoamperometry test

        scanrates : list(float)
            List of scan rates to be used in the CP [Vinit -> V1,V1 -> V2,V2 -> Vfinal]

        holdtimes : list(float) 
            List of hold times to be used in the CP [Apex1, Apex2, Final]

        Sample Period : float 
            Time between data-acquisition steps in seconds

        Max Cycle(int): 
            Number of cycles for the CP

        CtrlMode(Enumeration:CTRLMODE):
             Potentiostat control mode. GSTATMODE or PSTATMODE (for CA, we want PSTATMODE for controlling voltages)
        
        **kwargs 
            As of right now Kwargs are the stop at conditions for each curve. The compatible stop ats for CP experiments are:
                "vmax"
                "vmin"
            """

        self.voltage = voltage
        self.scanrates = scanrates
        self.holdtime = holdtime
        self.sample_time = sample_period
        self.maxcycles = maxcycles
        self.PSTATMODE = PSTATMODE
        super().__init__(kwargs)
        print(kwargs)
        
    def initialize_pstat(self, pstat): #removed third parameter "sampling rate"
            """This function is the standard initialization for ca experiments

            Parameters
            ----------
            pstat : toolkitpy.Pstat
                The desired pstat to change the hardware parameters
            sampling_rate : float
                The desired sampling rate of the experiment
            """
            
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

    

    def estimated_point_count(self):
        return int(self.holdtime / self.sample_time + 0.5)      

    def run_ca_test(self, pstat, voltage, holdtime, max_size = 100000):
        """Runs a Chronoamperometry test with the given parameters. Note: initialize the pstat with the initialize_pstat function before running this function.
        
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
            Returns some ND array with experiment data        """

        pstat.set_ctrl_mode(tkp.PSTATMODE) # potentiostatic mode (holding constant voltage)

        curve = tkp.ChronoACurve(pstat, max_size)

        self.initialize_pstat(pstat)
        
                                        #Vinit,  Time to run,   SamplePeriod,     CtrlMode
        signal = pstat.signal_const_new(voltage, holdtime, self.sample_time, tkp.PSTATMODE)

        pstat.set_signal_const(signal)
        
        pstat.init_signal()
        pstat.set_cell(True)
        points = self.estimated_point_count()
        
        tkp.log.info(f"Running CA experiment there will be ~{points} rows of data")
        print(curve)
        try:
            curve.run(True)
            t0 = time.time()
            last_print = 0
            while curve.running():
                time.sleep(0.1)
                data = curve.last_data_point()
                if LIVE_HOOK: LIVE_HOOK("CA", time.time() - t0, data['im'])
                if time.time() - last_print > 2:
                    print(f"point={data['point']:.3f}  vf={data['vf']:.3f}  im={data['im']:.3f}  t={time.time()-t0:.1f}")
                    last_print = time.time()
                
                
            t1 = time.time()
            print(t1-t0)

        finally:
            pstat.set_cell(False)

        data = curve.acq_data()
        if data['stop_test'][-1] != 0:
            tkp.log.info(f'Stop test occurred at point {data["point"]}')
        print("CA completed")
        self.is_run = True
        if self.PSTATMODE == tkp.PSTATMODE:
            self.last_value = data['vf'][-1]
        elif self.PSTATMODE == tkp.GSTATMODE:
            self.last_value = data['im'][-1]

        del signal

        return data


    def run_ca_test_looping(self, pstat, mux, channels, max_size = 100000):
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

        ensure_toolkit_init("ca.py")
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
        imx_list.sort()
        pstat_list.sort()
        print(pstat_list)
        
        mux.open()
        
        for cell in channels:        
            for i in range(8):
                mux.set_off_mode(i,tkp.MUX_CELL_LOCAL)

            mux.set_cell(cell)

            data = self.run_ca_test(pstat, 1, 0.1, max_size)
        
        
        mux.close()


def run_ca_cell(cell, voltage, time_run, output_file_name = "chronoamperometry", electrode_used = "Pt", path_to_save_to = r"C:\AttomRobotFiles\Data\DB_Ciara\ca", save_to_db_folder = True, standard = False, sample_period = 0.1):
    """Single blocking CA on one cell. Returns a DataFrame; triplet.write_measurement
    is the canonical writer (this function saves nothing itself)."""
    ensure_toolkit_init("ca.py")
    devices = tkp.enum_sections()
    imx_list = sorted(d for d in devices if d[0:3] == "IMX")
    pstat_list = sorted(d for d in devices if d[0:3] == "IFC")

    mux_pstat_index = cell // 8
    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])
    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
    mux.open()
    pstat.open()
    mux.set_cell(cell - mux_pstat_index * 8)

    ca = CA(voltage, [0.1, 0.1, 0.1], time_run, 1, sample_period, tkp.PSTATMODE)
    max_size = ca.estimated_point_count() + 1024
    try:
        data = ca.run_ca_test(pstat, voltage, time_run, max_size=max_size)
    finally:
        try:
            mux.close()
        except Exception:
            pass
        try:
            pstat.close()
        except Exception:
            pass

    df = pd.DataFrame(data)
    try:
        df["temp(C)"] = TemperWindows(vendor_id=0x3553, product_id=0xa001).get_temperature()[1]
    except Exception as e:
        print(f"temper read failed: {e!r}")
        df["temp(C)"] = float("nan")
    df["datetime"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    return df


def run_ca_multi(cells, voltage=1.0, time_run=3600, sample_period=1.0,
                 status_every=60, checkpoint_every=600, checkpoint_dir="res/ca",
                 stop_event=None):
    """Simultaneous CA on cells living on different muxes, e.g. (0, 8, 16).
    Returns {cell: DataFrame}. stop_event: optional threading.Event; set it to
    end the run early (collected data is still returned)."""
    if len(set(c // 8 for c in cells)) != len(cells):
        raise ValueError(f"one cell per mux only: {cells}")

    ensure_toolkit_init("ca.py")
    devices = tkp.enum_sections()
    imx_list = sorted(d for d in devices if d[0:3] == "IMX")
    pstat_list = sorted(d for d in devices if d[0:3] == "IFC")
    print("pstats:", pstat_list, "| muxes:", imx_list)

    os.makedirs(checkpoint_dir, exist_ok=True)
    rigs = []
    try:
        for cell in cells:
            idx = cell // 8
            pstat = tkp.Pstat("Pstat", pstat_list[idx])
            mux = tkp.IMX("IMX", imx_list[idx])
            mux.open()
            pstat.open()
            for i in range(8):
                mux.set_off_mode(i, tkp.MUX_CELL_OPEN)
            mux.set_cell(cell - idx * 8)

            ca = CA(voltage, [0.1, 0.1, 0.1], time_run, 1, sample_period, tkp.PSTATMODE)
            max_size = ca.estimated_point_count() + 1024
            pstat.set_ctrl_mode(tkp.PSTATMODE)
            curve = tkp.ChronoACurve(pstat, max_size)
            ca.initialize_pstat(pstat)
            signal = pstat.signal_const_new(voltage, time_run, sample_period, tkp.PSTATMODE)
            pstat.set_signal_const(signal)
            pstat.init_signal()
            pstat.set_cell(True)
            curve.run(True)
            rigs.append({"cell": cell, "pstat": pstat, "mux": mux, "curve": curve,
                         "signal": signal, "done": False, "ckpt_ok": True})
            print(f"cell {cell} started on {pstat_list[idx]} ch {cell - idx * 8}")

        t0 = time.time()
        last_status = last_ckpt = t0
        while not all(r["done"] for r in rigs):
            if stop_event is not None and stop_event.is_set():
                print("stop requested -- ending CA early")
                break
            time.sleep(1.0)
            now = time.time()
            for r in rigs:
                if not r["done"] and not r["curve"].running():
                    r["done"] = True
                    r["pstat"].set_cell(False)
                    print(f"cell {r['cell']} finished at t={now - t0:.0f}s")
            if now - last_status > status_every:
                for r in rigs:
                    if r["done"]:
                        continue
                    try:
                        d = r["curve"].last_data_point()
                        print(f"cell {r['cell']}  point={d['point']:.0f}  vf={d['vf']:.3f}  "
                              f"im={d['im']:.3e}  t={now - t0:.0f}s")
                    except Exception:
                        pass
                last_status = now
            if checkpoint_every and now - last_ckpt > checkpoint_every:
                for r in rigs:
                    if r["done"] or not r["ckpt_ok"]:
                        continue
                    try:
                        snap = pd.DataFrame(r["curve"].acq_data())
                        p = os.path.join(checkpoint_dir, f"ca_cell{r['cell']}_partial.csv")
                        snap.to_csv(p + ".tmp", index=False)
                        os.replace(p + ".tmp", p)
                    except Exception as e:
                        r["ckpt_ok"] = False
                        print(f"cell {r['cell']} checkpointing disabled: {e!r}")
                last_ckpt = now
    finally:
        for r in rigs:
            r["signal"] = None
            try:
                r["pstat"].set_cell(False)
            except Exception:
                pass
            try:
                r["mux"].close()
            except Exception:
                pass
            try:
                r["pstat"].close()
            except Exception:
                pass

    try:
        temp = TemperWindows(vendor_id=0x3553, product_id=0xa001).get_temperature()[1]
    except Exception as e:
        print(f"temper read failed: {e!r}")
        temp = float("nan")
    stamp = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    out = {}
    for r in rigs:
        try:
            df = pd.DataFrame(r["curve"].acq_data())
        except Exception as e:
            print(f"cell {r['cell']} acq_data failed: {e!r}")
            continue
        df["temp(C)"] = temp
        df["datetime"] = stamp
        out[r["cell"]] = df
    return out


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

def example_cp_test(cell): # not updated to CA tests
    ensure_toolkit_init("ca.py")

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



def run_cp_output(output_file_name,values = [[0.002, 0.002 ,0.002, 0.002], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1], electrode_used = "Pt", save_to_db_folder = True, standard = False):
    
    ensure_toolkit_init("ca.py")
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


def run_cp_cell(cell, current, time_run, output_file_name = "chronopotentiometry", electrode_used = "Pt", path_to_save_to = r"C:\AttomRobotFiles\Data\DB_Ciara\cp", save_to_db_folder = True, standard = False):
    values = [[0, current, current, 0], [0.1, 0.1, 0.1], [time_run/2, time_run/2, 0.05], 1, 0.1]
    """
    #Vinit, Tinit, Vstep1, Tstep1, Vstep2, Tstep2, SamplePeriod CtrlMode
    values
        amperage_list : list(float)
             List of amperages to be used in the CP [Iinit,I1,I2,Ifinal]

        scanrates : list(float)
            List of scan rates to be used in the CP [Iinit -> I1,I1 -> I2,I2 -> Ifinal]

        holdtimes : list(float) 
            List of hold times to be used in the CP [Apex1, Apex2, Final]
    """
    ensure_toolkit_init("ca.py")
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
    imx_list.sort()
    pstat_list.sort()

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
    mux.close()

    vf_diff,vf_max,vf_min  = cp_interpret(out_path)
    # overP, i0, alpha_c = kinetic_fit(out_path)
    new_row = pd.DataFrame([[output_file_name, vf_max, vf_min, vf_diff, None, None, None, temperature, curr_time]], columns=['test name', 'vf_max', 'vf_min', 'vf_diff',  "overP", "i0", "alpha_c", 'temp', 'time'])
    s_df = pd.concat([s_df, new_row], ignore_index=True)
    s_df.to_csv(s_df_file, index=False)

    if save_to_db_folder and not standard:
        return db_path

# still cp, not ca
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
    ensure_toolkit_init("ca.py")
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
    imx_list.sort()
    pstat_list.sort()

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


import threading
 
# fall back only if the live file doesn't already define these
try:
    LIVE_HOOK
except NameError:
    LIVE_HOOK = None
 
try:
    _ensure_tkp
except NameError:
    def _ensure_tkp():
        ensure_toolkit_init("ca.py")
 
CA_CYCLE_SETTLE_S = 0.01  # pause after a mux channel switch before energizing

 
 
def _plate_devices():
    """Sorted IMX / IFC section lists (sorted so mux i <-> pstat i stays stable)."""
    devices = tkp.enum_sections()
    imx_list = sorted(d for d in devices if d[:3] == "IMX")
    pstat_list = sorted(d for d in devices if d[:3] == "IFC")
    return imx_list, pstat_list

# # ====== Cycling CA v3: single curve per mux + COM diet ======
# # REPLACES ca_cycle_mux() and _ca_cycle_frames() in utils/PStat/ca.py.
# # Both defs at MODULE LEVEL (def at column 0).
# # v2 -> v3: no COM calls in the switch path except the switch itself
# # (harvests run every harvest_s off the critical path, switch anchors are
# # wall->hardware-time bounds recalibrated at each harvest, live hook is
# # throttled), plus loud detection if the acquisition dies early.

# CA_CYCLE_BLANK_S = 0.005    # discard window after each switch, hardware time
# CA_CYCLE_SWITCH_MARGIN_S = 0.020   # covers COM jitter in the wall->hw calibration


# def ca_cycle_mux(mux_idx, channels, voltage, overall_time, interval,
#                  sample_period=0.1, idle_mode="local", stop_event=None,
#                  checkpoint_s=600.0, checkpoint_cb=None, max_size=None,
#                  blank_s=CA_CYCLE_BLANK_S, harvest_s=5.0, live_hz=1.0,
#                  hot_switch=False):
#     """Round-robin CA on ONE mux with a single continuous acquisition.

#     One constant-V signal runs for the whole time; a channel switch is only
#     cell-off -> mux.set_cell -> cell-on (3 COM calls; 1 with hot_switch=True,
#     which leaves the pstat driving through the handoff -- only sane with
#     idle_mode='local' so both cells sit at `voltage` on the DAC).

#     Data is pulled with acq_data every `harvest_s` seconds, not at every
#     switch, and chopped afterwards using per-switch markers. Markers are
#     wall-clock stamps mapped onto the pstat's time base via an offset that is
#     re-measured at every harvest, biased so the marker can only ever be LATE:
#     kept data for each dwell starts within [blank_s, blank_s + sample_period
#     (+ a few ms of COM jitter)] after the relay -- for a ~10 ms settle, run
#     sample_period <= 0.01.

#     Returns {channel: DataFrame(Point, time, t_hold, Vf, Im, Cycle)}.
#     Prints switch-timing stats; prints a loud warning and ends the run if the
#     acquisition stops early (e.g. a firmware signal/point limit).
#     """
#     channels = [int(c) for c in channels]
#     if not channels:
#         raise ValueError("ca_cycle_mux: no channels given")
#     for c in channels:
#         if not 0 <= c <= 7:
#             raise ValueError(f"ca_cycle_mux: channel {c} out of range 0-7")
#     if interval < 2 * sample_period:
#         raise ValueError("ca_cycle_mux: interval must be >= 2 * sample_period")
#     if interval <= blank_s + sample_period + 0.02:
#         raise ValueError("ca_cycle_mux: interval too short for the blank window")
#     if stop_event is None:
#         stop_event = threading.Event()
#     if max_size is None:
#         max_size = int(float(overall_time) / float(sample_period)) + 4096

#     _ensure_tkp()
#     imx_list, pstat_list = _plate_devices()
#     if mux_idx >= len(imx_list) or mux_idx >= len(pstat_list):
#         raise RuntimeError(
#             f"ca_cycle_mux: mux {mux_idx} not available "
#             f"(found {len(imx_list)} IMX, {len(pstat_list)} IFC)")

#     pstat = tkp.Pstat("Pstat", pstat_list[mux_idx])
#     mux = tkp.IMX("IMX", imx_list[mux_idx])
#     mux.open()
#     pstat.open()

#     ca = CA(voltage, [0.1, 0.1, 0.1], interval, 1, sample_period, tkp.PSTATMODE, imax=50)

#     buffers = {c: {"time": [], "t_hold": [], "vf": [], "im": [], "cycle": []}
#                for c in channels}
#     hold_acc = {c: 0.0 for c in channels}
#     # per-dwell windows in hw time: keep points in [starts[k], ends[k])
#     # starts[k] = upper bound of switch end + blank; ends[k] = lower bound of
#     # the next cell-off (inf for the dwell in progress)
#     dw_start = [blank_s]
#     dw_end = [float("inf")]
#     dw_ch = [channels[0]]
#     dw_cy = [0]
#     dwell_first = {}   # dwell idx -> (first kept hw t, hold base at that t)
#     state = {"last_hw_t": -1.0, "synth_n": 0, "base": 0.0, "died": False}
#     switch_ms = []
#     pad = max(5.0, 2.0 * float(interval))
#     head_pad = sample_period + CA_CYCLE_SWITCH_MARGIN_S + blank_s

#     def _harvest(curve, wall_now):
#         d = curve.acq_data()
#         im = np.asarray(d['im'], dtype=float)
#         vf = np.asarray(d['vf'], dtype=float)
#         try:
#             tt = np.asarray(d['time'], dtype=float)
#         except Exception:
#             tt = (state["synth_n"] + np.arange(len(im))) * sample_period
#         state["synth_n"] += len(im)
#         new = tt > state["last_hw_t"] + 1e-9   # cumulative- and drained-safe
#         tt, vf, im = tt[new], vf[new], im[new]
#         if not len(tt):
#             return
#         state["last_hw_t"] = float(tt[-1])
#         # recalibrate wall->hw offset with a wall stamp taken AFTER acq_data
#         # returned, so hw_est(w) = (w - t_run0) - base is always <= true hw(w)
#         state["base"] = (time.time() - t_run0) - state["last_hw_t"]

#         st = np.asarray(dw_start, dtype=float)
#         en = np.asarray(dw_end, dtype=float)
#         idx = np.searchsorted(st, tt, side="right") - 1
#         keep = (idx >= 0) & (tt < en[np.clip(idx, 0, len(en) - 1)])
#         tt, vf, im, idx = tt[keep], vf[keep], im[keep], idx[keep]
#         for k in np.unique(idx):
#             m = idx == k
#             ts, vs, cs = tt[m], vf[m], im[m]
#             ch, cy = dw_ch[k], dw_cy[k]
#             if k not in dwell_first:
#                 dwell_first[k] = (float(ts[0]), hold_acc[ch])
#             first_t, hbase = dwell_first[k]
#             b = buffers[ch]
#             b["time"].extend(ts.tolist())
#             b["t_hold"].extend((hbase + (ts - first_t)).tolist())
#             b["vf"].extend(vs.tolist())
#             b["im"].extend(cs.tolist())
#             b["cycle"].extend([cy] * len(ts))
#             hold_acc[ch] = hbase + float(ts[-1] - first_t) + sample_period

#     curve = None
#     signal = None
#     aborted = False
#     cur_cycle = 0
#     try:
#         pstat.set_ctrl_mode(tkp.PSTATMODE)
#         ca.initialize_pstat(pstat)
#         for c in range(8):
#             if c in channels and idle_mode == "local":
#                 mux.set_off_mode(c, tkp.MUX_CELL_LOCAL)
#                 mux.set_dac(c, voltage)
#             else:
#                 mux.set_off_mode(c, tkp.MUX_CELL_OPEN)

#         signal = pstat.signal_const_new(voltage, float(overall_time) + pad,
#                                         sample_period, tkp.PSTATMODE)
#         pstat.set_signal_const(signal)
#         pstat.init_signal()
#         curve = tkp.ChronoACurve(pstat, max_size)
#         mux.set_cell(channels[0])
#         pstat.set_cell(True)
#         t_run0 = time.time()          # wall stamp BEFORE run: hw 0 is at/after this
#         curve.run(True)
#         t0_wall = time.time()
#         try:   # seed the wall->hw offset (one COM call, start of run only)
#             state["base"] = (time.time() - t_run0) - float(curve.last_data_point()['time'])
#         except Exception:
#             state["base"] = time.time() - t_run0

#         cur_idx = 0
#         slot = 1
#         last_ckpt = t0_wall
#         last_harvest = t0_wall
#         last_live = 0.0

#         while True:
#             slot_end = t0_wall + slot * float(interval)
#             while True:
#                 now = time.time()
#                 if now >= slot_end:
#                     break
#                 if stop_event.is_set():
#                     aborted = True
#                     break
#                 time.sleep(min(0.05, max(slot_end - now, 0.001)))
#                 now = time.time()
#                 if LIVE_HOOK and live_hz > 0 and now - last_live >= 1.0 / live_hz:
#                     last_live = now
#                     try:
#                         ld = curve.last_data_point()
#                         LIVE_HOOK("CA", float(ld['time']), float(ld['im']))
#                     except Exception:
#                         pass
#                 if now - last_harvest >= harvest_s:
#                     last_harvest = now
#                     _harvest(curve, now)
#                     try:
#                         alive = curve.running()
#                     except Exception:
#                         alive = True
#                     if not alive and (now - t0_wall) < float(overall_time) - 1.0:
#                         state["died"] = True
#                         print(f"*** CA cycle mux{mux_idx}: ACQUISITION ENDED EARLY at "
#                               f"hw t~{state['last_hw_t']:.1f}s of {overall_time}s "
#                               f"(signal/point limit?) -- stopping and keeping data")
#                         break
#                     if checkpoint_cb and now - last_ckpt >= checkpoint_s:
#                         try:
#                             checkpoint_cb(_ca_cycle_frames(buffers))
#                         except Exception:
#                             import traceback
#                             traceback.print_exc()
#                         last_ckpt = now

#             if aborted or state["died"] or (time.time() - t0_wall) >= float(overall_time):
#                 break

#             # ---- the switch: 3 COM calls (1 if hot) ----
#             nxt = (cur_idx + 1) % len(channels)
#             sw0 = time.time()
#             if hot_switch:
#                 mux.set_cell(channels[nxt])
#             else:
#                 pstat.set_cell(False)
#                 mux.set_cell(channels[nxt])
#                 pstat.set_cell(True)
#             sw1 = time.time()
#             switch_ms.append((sw1 - sw0) * 1000.0)
#             # hw_est() is a calibrated LOWER bound of true hw time, so:
#             # old dwell ends at hw_est(sw0); new dwell starts at
#             # hw_est(sw1) + sample_period + margin (an upper bound) + blank
#             dw_end[-1] = (sw0 - t_run0) - state["base"]
#             dw_start.append((sw1 - t_run0) - state["base"] + head_pad)
#             dw_end.append(float("inf"))
#             if nxt == 0:
#                 cur_cycle += 1
#             dw_ch.append(channels[nxt])
#             dw_cy.append(cur_cycle)
#             cur_idx = nxt
#             slot += 1

#         _harvest(curve, time.time())   # final pull

#         try:
#             pstat.set_cell(False)
#         except Exception:
#             pass
#         stopper = getattr(curve, "stop", None)
#         if callable(stopper):
#             try:
#                 stopper()
#             except Exception:
#                 pass
#             t_limit = time.time() + 3.0
#         else:
#             t_limit = time.time() + (3.0 if (aborted or state["died"]) else pad + 5.0)
#         try:
#             while curve.running() and time.time() < t_limit:
#                 time.sleep(0.2)
#         except Exception:
#             pass
#     finally:
#         for _f in (lambda: pstat.set_cell(False),
#                    lambda: mux.set_cell(False),
#                    lambda: mux.close(),
#                    lambda: pstat.close()):
#             try:
#                 _f()
#             except Exception:
#                 pass

#     if switch_ms:
#         s = sorted(switch_ms)
#         print("*** CA cycle mux{}: {} cycles, {} switches | switch ms "
#               "mean {:.0f} / p95 {:.0f} / max {:.0f} | head discard <= {:.0f} ms{}".format(
#                   mux_idx, cur_cycle, len(switch_ms),
#                   sum(s) / len(s), s[int(0.95 * (len(s) - 1))], s[-1],
#                   head_pad * 1000.0,
#                   " | DIED EARLY" if state["died"] else ""))
#     return _ca_cycle_frames(buffers)


# def _ca_cycle_frames(buffers):
#     out = {}
#     for ch, b in buffers.items():
#         n = len(b["time"])
#         out[ch] = pd.DataFrame({"Point": np.arange(n),
#                                 "time": b["time"],
#                                 "t_hold": b["t_hold"],
#                                 "Vf": b["vf"],
#                                 "Im": b["im"],
#                                 "Cycle": b["cycle"]})
#     return out

def _ca_cycle_frames(buffers):
    out = {}
    for ch, b in buffers.items():
        n = len(b["time"])
        out[ch] = pd.DataFrame({"Point": np.arange(n),
                                "time": b["time"],
                                "Vf": b["vf"],
                                "Im": b["im"],
                                "Cycle": b["cycle"]})
    return out
     
def ca_cycle_mux(mux_idx, channels, voltage, overall_time, interval,
                 sample_period=0.1, idle_mode="local", stop_event=None,
                 checkpoint_s=600.0, checkpoint_cb=None, max_size=100000,
                 settle_skip_s=0.00):
    """
    idle_mode: "local" -> selected channels are parked on the mux DAC at
               `voltage` between dwells (stay biased); "open" -> disconnected.
               Unselected channels on this mux are always OPEN.
    checkpoint_cb: optional callable({channel: DataFrame}) invoked every
               `checkpoint_s` seconds with the partial data so far.
 
    Returns {channel: DataFrame(Point, time, Vf, Im, Cycle)} where `time` is
    seconds since the run started (global clock, so the gaps while other
    channels were active are visible in the data).
    """
    channels = [int(c) for c in channels]
    if not channels:
        raise ValueError("ca_cycle_mux: no channels given")
    for c in channels:
        if not 0 <= c <= 7:
            raise ValueError(f"ca_cycle_mux: channel {c} out of range 0-7")
    if interval < 2 * sample_period:
        raise ValueError("ca_cycle_mux: interval must be >= 2 * sample_period")
    if interval <= settle_skip_s + 2 * sample_period:
        raise ValueError("ca_cycle_mux: interval too short for settle_skip_s")
    if stop_event is None:
        stop_event = threading.Event()
 
    _ensure_tkp()
    imx_list, pstat_list = _plate_devices()
    if mux_idx >= len(imx_list) or mux_idx >= len(pstat_list):
        raise RuntimeError(
            f"ca_cycle_mux: mux {mux_idx} not available "
            f"(found {len(imx_list)} IMX, {len(pstat_list)} IFC)")
 
    pstat = tkp.Pstat("Pstat", pstat_list[mux_idx])
    mux = tkp.IMX("IMX", imx_list[mux_idx])
    mux.open()
    pstat.open()

    # time.sleep(0.04)
    ca = CA(voltage, [0.1, 0.1, 0.1], interval, 1, sample_period, tkp.PSTATMODE, imax=50)
    buffers = {c: {"time": [], "vf": [], "im": [], "cycle": []} for c in channels}
    t0 = time.time()
    deadline = t0 + float(overall_time)
    last_ckpt = t0
    cycle = 0
 
    try:
        pstat.set_ctrl_mode(tkp.PSTATMODE)
        ca.initialize_pstat(pstat)
 
        for c in range(8):
            if c in channels and idle_mode == "local":
                mux.set_off_mode(c, tkp.MUX_CELL_LOCAL)
                mux.set_dac(c, voltage)
            else:
                mux.set_off_mode(c, tkp.MUX_CELL_OPEN)
 
        while not stop_event.is_set() and time.time() < deadline:
            progressed = False
            for ch in channels:
                now = time.time()
                if stop_event.is_set() or now >= deadline:
                    break
                dwell = min(float(interval), deadline - now)
                if dwell < settle_skip_s + max(2.0 * sample_period, 0.05):
                    break
 
                mux.set_cell(ch)
                time.sleep(CA_CYCLE_SETTLE_S)
 
                signal = pstat.signal_const_new(voltage, dwell, sample_period, tkp.PSTATMODE)
                pstat.set_signal_const(signal)
                pstat.init_signal()
                time.sleep(0.01)
                curve = tkp.ChronoACurve(pstat, max_size)
                dwell_wall0 = time.time()
                aborted_at = None
                pstat.set_cell(True)
                try:
                    curve.run(True)
                    while curve.running():
                        if stop_event.is_set():
                            aborted_at = time.time()
                            break
                        time.sleep(min(0.1, sample_period))
                        try:
                            if LIVE_HOOK and time.time() - dwell_wall0 >= settle_skip_s:
                                d = curve.last_data_point()
                                LIVE_HOOK("CA", time.time() - t0, d['im'])
                        except Exception:
                            pass
                finally:
                    pstat.set_cell(False)
 
                d = curve.acq_data()
                im = np.asarray(d['im'], dtype=float)
                vf = np.asarray(d['vf'], dtype=float)
                try:
                    tt = np.asarray(d['time'], dtype=float)
                except Exception:
                    tt = np.arange(len(im)) * sample_period
                if aborted_at is not None:   # drop any cell-off tail points
                    keep = tt <= (aborted_at - dwell_wall0) + sample_period
                    tt, vf, im = tt[keep], vf[keep], im[keep]
                keep = tt >= settle_skip_s   # drop the switch/energize transient
                tt, vf, im = tt[keep], vf[keep], im[keep]
 
                b = buffers[ch]
                b["time"].extend(((dwell_wall0 - t0) + tt).tolist())
                b["vf"].extend(vf.tolist())
                b["im"].extend(im.tolist())
                b["cycle"].extend([cycle] * len(tt))
                del signal
                del curve
                progressed = True
 
            if not progressed:
                break
            cycle += 1
 
            if checkpoint_cb and time.time() - last_ckpt >= checkpoint_s:
                try:
                    checkpoint_cb(_ca_cycle_frames(buffers))
                except Exception:
                    import traceback
                    traceback.print_exc()
                last_ckpt = time.time()
    finally:
        for _f in (lambda: pstat.set_cell(False),
                   lambda: mux.set_cell(False),
                   lambda: mux.close(),
                   lambda: pstat.close()):
            try:
                _f()
            except Exception:
                pass
 
    print(f"*** CA cycle mux{mux_idx} done: {cycle} full cycles over "
          f"{time.time() - t0:.0f}s on channels {channels}")
    return _ca_cycle_frames(buffers)
 


'''
if __name__ == "__main__":
    tkp.toolkitpy_init("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    cv = CV([0, 1, -1, 0], [0.1, 0.1, 0.1], [0.05, 0.05, 0.05], 1, 0.1, tkp.PSTATMODE, imax = 10)
    data = cv.run(pstat)
    np.savetxt("test.csv", data, delimiter = ',', header = 'Point, time, Vf, Vu, Im, Ach, vsig, temp, Cycle, ie_range, overload, stop_test', fmt = '%s')
'''