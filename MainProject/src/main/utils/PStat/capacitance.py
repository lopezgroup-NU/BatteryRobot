# capacitance.py
# "Capacitance" testing protocol: one full CV cycle at each scan rate inside a
# fixed (non-faradaic) potential window; capacitance = zero-intercept slope of
# |I| at the window midpoint vs scan rate.
#
# Follows the plate-runner contract: run_capacitance_cell returns a DataFrame
# (all rates concatenated, tagged by scan_rate_mV_s) and triplet.write_measurement
# is the canonical writer. FIX: all analysis outputs (per-rate points CSV with
# the fitted summary columns + the two PNGs) are written into the CELL FOLDER
# next to the measurement CSVs by the GUI hook
# (dataanalysis.save_capacitance_graphs_from_df on meas.path). This module
# writes nothing outside the measurement pipeline anymore -- no res/ folders.

import datetime

import numpy as np
import pandas as pd
import toolkitpy as tkp
import time

from .cv import CV, CV_EQUIL_S, _ensure_tkp
from .dataanalysis import capacitance_interpret

DEFAULT_SCAN_RATES_MV_S = [5, 10, 25, 50, 100, 150, 200, 250]
DEFAULT_V_LOW = 0.8            # V -- override per call or via PARAM_DEFAULTS["CAPACITANCE"]
DEFAULT_V_HIGH = 1.0           # V
TARGET_POINTS_PER_CYCLE = 400
_RENAME = {"point": "Point", "vf": "Vf", "vu": "Vu", "im": "Im", "ach": "Ach",
           "cycle": "Cycle"}


def _sample_period(v_low, v_high, rate_mV_s):
    """Sample period scaled per scan rate so every cycle has similar resolution."""
    span = 2 * abs(v_high - v_low)                     # V traveled in one cycle
    sp = span / (rate_mV_s / 1000.0) / TARGET_POINTS_PER_CYCLE
    return round(min(max(sp, 0.01), 1.0), 4)


def _run_rates(pstat, output_file_name, v_low, v_high, scan_rates_mV_s, hold_s, stop_event):
    """One CV cycle per scan rate on an already-selected pstat/cell.
    Returns ({rate: DataFrame(Vf/Im/...)}, stopped_early). A rate interrupted
    mid-sweep is discarded (a partial cycle would corrupt the fit)."""
    cycles = {}
    for rate in scan_rates_mV_s:
        if stop_event is not None and stop_event.is_set():
            return cycles, True
        rate_V_s = rate / 1000.0
        sp = _sample_period(v_low, v_high, rate)
        cv = CV([v_low, v_high, v_low, v_low], [rate_V_s] * 3, [hold_s] * 3,
                1, sp, tkp.PSTATMODE, imax=10, guilherme_mode=False)
        print(f"[CAP] {output_file_name}: {rate} mV/s (sample period {sp} s)")
        data = cv.run_cv(pstat, stop_event=stop_event, equil_s = CV_EQUIL_S)
        if getattr(cv, "stopped_early", False):
            return cycles, True
        df = pd.DataFrame(data).rename(columns=_RENAME)
        df["scan_rate_mV_s"] = rate
        cycles[rate] = df
    return cycles, False


def _finish(cycles, output_file_name, v_low, v_high, target_voltage):
    """Analysis + combined DataFrame (the runner's return value).
    FIX: writes no files -- the points CSV and PNGs land in the cell folder
    via the GUI hook (dataanalysis.save_capacitance_graphs_from_df on
    meas.path). This computes, prints the result, and returns the data."""
    combined = pd.concat(cycles.values(), ignore_index=True)
    combined["datetime"] = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")

    if len(cycles) < 2:
        print(f"[CAP] {output_file_name}: only {len(cycles)} complete rate(s) -- "
              f"raw data kept, capacitance fit skipped")
        return combined

    # target defaults to the midpoint of the CONFIGURED window (0.9 V for
    # 0.8-1.0). Never derive it from measured Vf: startup samples taken before
    # the signal engages sit near the rest potential and drag the midpoint down.
    if target_voltage is None:
        target_voltage = (v_low + v_high) / 2.0
    result = capacitance_interpret(cycles, target_voltage=target_voltage, current_units="A")
    print(f"[CAP] {output_file_name}: C_avg={result['capacitance_avg_mF']:.4f} mF "
          f"(anodic {result['capacitance_anodic_mF']:.4f} / cathodic {result['capacitance_cathodic_mF']:.4f}, "
          f"R2 {result['r2_anodic']:.4f}/{result['r2_cathodic']:.4f})")
    return combined


def run_capacitance_cell(cell, output_file_name="capacitance",
                         v_low=DEFAULT_V_LOW, v_high=DEFAULT_V_HIGH,
                         scan_rates_mV_s=None, hold_s=0.05, target_voltage=None,
                         standard=False, stop_event=None):
    """Capacitance protocol on one plate cell (0-23). Returns a DataFrame with
    every rate's cycle (scan_rate_mV_s column); triplet.write_measurement is
    the canonical writer. Returns None if nothing completed."""
    scan_rates_mV_s = scan_rates_mV_s or DEFAULT_SCAN_RATES_MV_S

    _ensure_tkp("open_circuit_voltage.py")
    device_list = tkp.enum_sections()
    imx_list = sorted(d for d in device_list if d[0:3] == "IMX")
    pstat_list = sorted(d for d in device_list if d[0:3] == "IFC")
    mux_pstat_index = 0 if cell < 8 else 1 if cell < 16 else 2
    
    if mux_pstat_index >= len(pstat_list):
        raise RuntimeError(
            f"cell {cell} needs plate pstat #{mux_pstat_index} but only {pstat_list} are visible")
    pstat = tkp.Pstat("Pstat", pstat_list[mux_pstat_index])
    mux = tkp.IMX("IMX", imx_list[mux_pstat_index])
    try:
        mux.open()
        time.sleep(5)
        active_ch = cell - mux_pstat_index * 8
        for ch in range(8):
            if ch != active_ch:
                mux.set_off_mode(ch, tkp.MUX_CELL_LOCAL)
                mux.set_dac(ch, 0.0)
        mux.set_cell(active_ch)

        cycles, stopped = _run_rates(pstat, output_file_name, v_low, v_high,
                                     scan_rates_mV_s, hold_s, stop_event)
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

    if not cycles:
        print(f"[CAP] cell {cell} {output_file_name}: stopped before any rate completed")
        return None
    if stopped:
        print(f"[CAP] cell {cell} {output_file_name}: stopped early -- "
              f"keeping the {len(cycles)} completed rate(s)")
    return _finish(cycles, output_file_name, v_low, v_high, target_voltage)  # FIX: standard kwarg retained on the runner for compat; res/ outputs removed


def run_capacitance(output_file_name="capacitance",
                    v_low=DEFAULT_V_LOW, v_high=DEFAULT_V_HIGH,
                    scan_rates_mV_s=None, hold_s=0.05, target_voltage=None,
                    standard=False, stop_event=None):
    """Capacitance protocol on the bench pstat (no mux). Same return contract."""
    scan_rates_mV_s = scan_rates_mV_s or DEFAULT_SCAN_RATES_MV_S
    # Delay by like 5 seconds

    _ensure_tkp("open_circuit_voltage.py")
    pstat = tkp.Pstat("PSTAT")
    try:
        cycles, stopped = _run_rates(pstat, output_file_name, v_low, v_high,
                                     scan_rates_mV_s, hold_s, stop_event)
    finally:
        try:
            pstat.set_cell(False)
        except Exception:
            pass

    if not cycles:
        print(f"[CAP] {output_file_name}: stopped before any rate completed")
        return None
    if stopped:
        print(f"[CAP] {output_file_name}: stopped early -- keeping the {len(cycles)} completed rate(s)")
    return _finish(cycles, output_file_name, v_low, v_high, target_voltage)  # FIX: standard kwarg retained on the runner for compat; res/ outputs removed