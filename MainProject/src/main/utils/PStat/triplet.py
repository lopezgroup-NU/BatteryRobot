# NOTE: 2 Dummies (0, 1) and 1 nonDummy (7)
# NOTE: use get_time_stamp(); def in MathUtils.py
# Ask G on Wednesday to see if need firmware update

# NOTE: redundancy for multiple runs of the same test on the same cell
# NOTE: Fix device sorting in PEIS, CV, and CA

# NOTE: Set up overnight CA runs for three muxes on calibration cells

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime as dt
from pathlib import Path

from utils.PStat.peis import *
from utils.PStat.cv import *
from utils.PStat.ca import *
from GUI.triplet_gui import *
from utils.PStat.triplet_analysis import *
try:
    from utils.PStat.default_analysis import compute_default_analysis, analysis_subdoc
except ImportError:
    from default_analysis import compute_default_analysis, analysis_subdoc

import csv
import pandas as pd
import copy
import logging  # FIX (cleanup): used by run_test_cell; was only via star imports
import uuid

# ======= Data Types =======

@dataclass
# each measurement is one test ran on one cell
class Measurement:
    row: int                       # 1 - 6
    column: str                    # A - D
    electrochemical_test: str      # "CV", "PEIS", "CA"
    start_time: dt = field(default_factory=dt.now)
    finish_time: dt | None = None
    params: dict = field(default_factory=dict)
    data: pd.DataFrame | None = None

    @property
    def cell_id(self) -> str:
        return f"{self.row}{self.column}"

    @property
    def cell_num(self) -> int:
        return (self.row - 1) * 4 + ord(self.column.upper()) - ord('A')


@dataclass
# each run
class Plate:
    plate_id: str = field(default_factory=lambda: dt.now().strftime("%Y%m%d_%H_%M"))
    created_at: dt = field(default_factory=dt.now)
    config: dict = field(default_factory=dict)
    measurements: list[Measurement] = field(default_factory=list)


# ======= Export =======

# Export Constants
DATA_DIRECTORY = "C:\\AttomRobotFiles\\Software\\BatteryRobot\\MainProject\\src\\main\\res\\ciara_new_data\\data"
SAMPLE_LOG_DIRECTORY = "C:\\AttomRobotFiles\\Software\\BatteryRobot\\MainProject\\src\\main\\res\\ciara_new_data\\sample\\sample_log.csv"
PLATE_LOG_DIRECTORY = "C:\\AttomRobotFiles\\Software\\BatteryRobot\\MainProject\\src\\main\\res\\ciara_new_data\\plate\\plate_log.csv"

AUTO_ANALYZE = True  # regenerate plots after every test (triplet_analysis.analyze_cell_folder)

# Headers for log files
SAMPLE_LOG_COLS = ["plateID", "Date", "Operator", "Hypothesis", "Notes"]
PLATE_LOG_COLS = ["PlateID", "Cell Position", "Material Name", "Catalyst Loading",
                  "Nafion Loading", "Carbon Black Loading", "Extracted Data", "Comments"]


# file names
def _stem(plate_id: str, cell_id: str) -> str:   # base file name
    return f"{plate_id}_{cell_id}"

def _data_filename(plate_id: str, cell_id: str, test: str) -> str:
    return f"{_stem(plate_id, cell_id)}_{test}.csv"

def _meta_filename(plate_id: str, cell_id: str, test: str) -> str:
    return f"{_stem(plate_id, cell_id)}_{test}_meta.csv"


# writes measurements
def write_measurement(measurement, plate_id: str, root: str | Path = ".") -> tuple[Path | None, Path]:
    """Write one measurement instance with its meta CSV. Returns (data_path, meta_path)."""
    cell_dir = Path(root) / DATA_DIRECTORY / _stem(plate_id, measurement.cell_id)
    cell_dir.mkdir(parents=True, exist_ok=True)        # create the per-cell folder

    data_path = cell_dir / _data_filename(plate_id, measurement.cell_id, measurement.electrochemical_test)
    meta_path = cell_dir / _meta_filename(plate_id, measurement.cell_id, measurement.electrochemical_test)

    # data: guard against an aborted/empty run
    if measurement.data is not None:
        measurement.data.to_csv(data_path, index=False)
    else:
        data_path = None  # no data (e.g. serial loss or aborted test); metadata is still stored

    rows = [
        ("plateID", plate_id),
        ("cell_id", measurement.cell_id),
        ("row", measurement.row),
        ("column", measurement.column),
        ("cell_num", measurement.cell_num),
        ("electrochemical_test", measurement.electrochemical_test),
        ("start_time", measurement.start_time.isoformat() if measurement.start_time else ""),
        ("finish_time", measurement.finish_time.isoformat() if measurement.finish_time else ""),
        ("n_points", 0 if measurement.data is None else len(measurement.data)),  # data points collected
    ]
    rows += [(k, measurement.params[k]) for k in sorted(measurement.params)]
    try:
        rows += list(compute_default_analysis(
            measurement.electrochemical_test, measurement.data, measurement.params).items())
    except Exception as e:
        rows += [("analysis_error", repr(e))]
    with open(meta_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["field", "value"])
        w.writerows(rows)

    upload_cell_run(plate_id, measurement.cell_id, measurement.cell_num,
                    measurement.electrochemical_test, measurement.params,
                    measurement.start_time, data_path, data_df=measurement.data)

    # ---- auto-analysis: regenerate this cell's plots after every test ----
    if AUTO_ANALYZE:
        try:
            try:
                from utils.PStat.triplet_analysis import analyze_cell_folder
            except ImportError:
                from triplet_analysis import analyze_cell_folder
            analyze_cell_folder(cell_dir)
        except Exception as e:
            print(f"[analysis] plot generation failed for {cell_dir}: {e}")
    return data_path, meta_path

# Logs
def _upsert_csv_row(path: Path, columns: list[str], key_cols: list[str], row: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and path.stat().st_size > 0:
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=columns)
        for c in columns:
            if c not in df.columns:
                df[c] = ""
        df = df[columns + [c for c in df.columns if c not in columns]]  # FIX (cleanup): keep extra columns (GUI Cell Notes)
    else:
        df = pd.DataFrame(columns=columns)

    new_row = {c: ("" if row.get(c) is None else str(row.get(c, ""))) for c in columns}
    mask = pd.Series([True] * len(df), index=df.index)
    for k in key_cols:
        mask &= df[k].astype(str) == str(new_row[k])

    if len(df) and mask.any():
        idx = df.index[mask][0]
        for c in columns:
            df.at[idx, c] = new_row[c]
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    df.to_csv(path, index=False)
    return path

def _resolve_params(plate, test, explicit=None):
    merged = copy.deepcopy(PARAM_DEFAULTS.get(test, {})) 
    merged.update(plate.config.get(f"{test.lower()}_params") or {})
    if explicit:
        merged.update(explicit)
    return merged

# records one run
def record_sample(plate_id: str, date, operator: str = "", hypothesis: str = "", notes: str = "", root: str | Path = ".") -> Path:
    if isinstance(date, dt):
        date = date.strftime("%Y%m%d")
    # input_notes = input("Notes for Sample Log: ")
    return _upsert_csv_row(Path(root) / SAMPLE_LOG_DIRECTORY, SAMPLE_LOG_COLS, ["plateID"],
                           {"plateID": plate_id, "Date": date, "Operator" : operator, "Hypothesis" : hypothesis, "Notes": notes})


# records a plate cell
def record_plate_cell(plate_id: str, cell_id: str, material_name: str = "", catalyst_loading="",
                      nafion_loading="", carbon_black_loading="", extracted_data="", comments: str = "",
                      root: str | Path = ".") -> Path:
    return _upsert_csv_row(Path(root) / PLATE_LOG_DIRECTORY, PLATE_LOG_COLS, ["PlateID", "Cell Position"],
                           {"PlateID": plate_id, "Cell Position": cell_id, "Material Name": material_name,
                            "Catalyst Loading": catalyst_loading, "Nafion Loading": nafion_loading,
                            "Carbon Black Loading": carbon_black_loading, "Extracted Data": extracted_data,
                            "Comments": comments})



# ====== Measurements ======

# change tests without rerunning
ACTIVE_TESTS = ["PEIS", "CV"]

def set_tests(*names):
    """Change the default test list without restarting, e.g. set_tests('PEIS', 'CA')."""
    names = [n.strip().upper() for n in names]
    if not names:
        raise ValueError("Give at least one test name.")
    unknown = [n for n in names if n not in TEST_RUNNERS]
    if unknown:
        raise ValueError(f"Unknown test(s): {unknown}. Available: {list(TEST_RUNNERS)}")
    global ACTIVE_TESTS
    ACTIVE_TESTS = names
    print(f"Active tests: {ACTIVE_TESTS}")
    return ACTIVE_TESTS

# Each runner: (cell, params, name) -> DataFrame (None/raise on failure)
# NOTE: these also pass output_file_name to the hardware function, which writes its OWN copy
# in its own folder (PEIS/CV only; CA saves nothing itself -- write_measurement is its only writer).
# Default measurement parameters per test. Override per plate via config["peis_params"] etc.

PARAM_DEFAULTS = {
    "PEIS": {"initial_freq": 10000, "final_freq": 10, "ac_voltage": 0.02, "dc_voltage": 0.0,
             "estimated_z": 100, "points_per_decade": 10, "max_bad_reads": 1},
    "CV": {
        "voltage_list":  [1, 1.65, 1.08, 1],
        "scan_rates":    [0.01, 0.01, 0.01],
        "hold_times":    [0.05, 0.05, 0.05],
        "maxcycle":      2,
        "sample_period": 0.1,
    },
    "CA": {"voltage": 1.8, "time_run": 120, "sample_period": 0.1},
}

import os
import threading
 
PARAM_DEFAULTS["CA_CYCLE"] = {
    "voltage": 1.8, 
    "overall_time": 7200.0,  # total seconds for the whole run
    "interval": 0.1,        # seconds spent on each cell before switching
    "sample_period": 0.0001,    # s between points
    "idle_mode": "local",    # "local": mux DAC holds selected cells at `voltage; "open": disconnected
    "checkpoint_s": 600.0,   # partial-CSV flush in case of failures; probably update to shorter intervals
}
 
 
def _ca_cycle_csv_path(plate_id, cell_id, root="."):
    cell_dir = Path(root) / DATA_DIRECTORY / _stem(plate_id, cell_id)
    cell_dir.mkdir(parents=True, exist_ok=True)
    return cell_dir / _data_filename(plate_id, cell_id, "CA_CYCLE")
 
 
def _atomic_csv(df, path):
    tmp = Path(str(path) + ".tmp")
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)
 
 
def run_ca_cycle_mux(plate, mux_idx, hw_cells, params=None, root=".", stop_event=None):
    """One mux's share of a cycling-CA run: drives ca_cycle_mux() and records
    one CA_CYCLE Measurement per cell through the normal pipeline. Call from
    one thread per mux (the GUI's CA Cycle does this)."""
    resolved = _resolve_params(plate, "CA_CYCLE", params)
    hw_cells = sorted({int(c) for c in hw_cells})
    for c in hw_cells:
        if c // 8 != mux_idx:
            raise ValueError(f"cell {c} is not on mux {mux_idx}")
    ch_to_hw = {c % 8: c for c in hw_cells}
 
    def _cell_id(hw):
        return f"{hw // 4 + 1}{'ABCD'[hw % 4]}"
 
    def _checkpoint(partial):   # {channel: df} -> partial CSVs at the final paths
        for ch, df in partial.items():
            _atomic_csv(df, _ca_cycle_csv_path(plate.plate_id, _cell_id(ch_to_hw[ch]), root))
 
    start = dt.now()
    dfs = ca_cycle_mux(mux_idx=mux_idx,
                       channels=sorted(ch_to_hw),
                       voltage=float(resolved["voltage"]),
                       overall_time=float(resolved["overall_time"]),
                       interval=float(resolved["interval"]),
                       sample_period=float(resolved["sample_period"]),
                       idle_mode=str(resolved.get("idle_mode", "local")).lower(),
                       stop_event=stop_event,
                       checkpoint_s=float(resolved.get("checkpoint_s", 600.0)),
                       checkpoint_cb=_checkpoint)
    finish = dt.now()
 
    out = []
    for ch, df in dfs.items():
        hw = ch_to_hw[ch]
        m = Measurement(row=hw // 4 + 1, column="ABCD"[hw % 4],
                        electrochemical_test="CA_CYCLE",
                        start_time=start, finish_time=finish,
                        params={**resolved, "hw_cell": hw, "mux": mux_idx,
                                "cells_in_run": hw_cells},
                        data=df)
        plate.measurements.append(m)
        write_measurement(m, plate.plate_id, root)
        out.append(m)
    return out
 
 
# ---- Utils ---- #

def _run_peis(cell, params, name):
    return run_peis_cell(cell, output_file_name=name, parameter_list=params)

def _run_cv(cell, params, name):
    values = [params["voltage_list"], params["scan_rates"], params["hold_times"],
              params["maxcycle"], params["sample_period"]]
    return run_cv_cell(cell, output_file_name=name, values=values)


def _run_ca(cell, params, name):
    return run_ca_cell(cell, output_file_name=name,
                       voltage=params.get("voltage", 1.0),
                       time_run=params.get("time_run", 30),
                       sample_period=params.get("sample_period", 0.1))

def _resolve_cell(plate, row, column) -> int:
    """Hardware index (0-23, mux = index // 8) for a plate position: row-major."""
    return (row - 1) * 4 + ord(column.upper()) - ord("A")

# ---- Things that actually make things run ---- #

TEST_RUNNERS = {"PEIS": _run_peis, "CV": _run_cv, "CA": _run_ca}

from utils.PStat.capacitance import run_capacitance_cell

PARAM_DEFAULTS["CAPACITANCE"] = {
    "v_low": 0.8, "v_high": 1.0,
    "scan_rates_mV_s": [5, 10, 25, 50, 100, 150, 200, 250],
    "hold_s": 0.05, "target_voltage": None,
}

def _run_capacitance(cell, params, name):
    return run_capacitance_cell(cell, output_file_name=name,
                                v_low=params["v_low"], v_high=params["v_high"],
                                scan_rates_mV_s=params["scan_rates_mV_s"],
                                hold_s=params.get("hold_s", 0.05),
                                target_voltage=params.get("target_voltage"))

TEST_RUNNERS["CAPACITANCE"] = _run_capacitance

# FIX (mux cycle): defaults for the GUI's Mux Cycle dialog (also shows up as a
# MUX_CYCLE tab in Settings). Each test still runs with its own tab's params,
# e.g. the CA hold is CA -> time_run. Arm points live in plate_locations.py.
PARAM_DEFAULTS["MUX_CYCLE"] = {
    "tests": ["PEIS", "CV", "CA"],   # run in this order on every selected cell
    "liquid_mode": "none",           # "draw" | "simulate" | "none"
    "volume_ml": 1.0,                # draw: mL into each cell (1 mL per pipette trip)
    "ca_back_s": 60.0,               # FIX (CA_Back): FULL only -- s spent revisiting every finished cell on the mux after each new CA hold
    "ca_end_s": 0.0,                 # FIX (CA_End): FULL only -- s cycling ALL the mux's cells once its last cell is done (0 = off)
    "full": False,                   # FIX (FULL toggle): Mux Cycle's "FULL cycle" checkbox
}

TEST_ALIASES = {"CAP": "CAPACITANCE"}

def canon_test(name):
    """Canonical test name, e.g. "CAP" -> "CAPACITANCE"."""
    t = str(name).strip().upper()
    return TEST_ALIASES.get(t, t)

def measure(plate, row, column, test, params=None, root="."):
    """Run a single `test` on one cell, store it on `plate`, and write it to disk."""
    test = canon_test(test)
    cell = _resolve_cell(plate, row, column)
    cell_id = f"{row}{column}"
    output_name = f"{plate.plate_id}_{cell_id}_{test}"
    resolved = _resolve_params(plate, test, params)
    start_time = dt.now()
    try:
        data = TEST_RUNNERS[test](cell, resolved, output_name)
    except Exception as e:
        print(f"[{test} {cell_id}] failed: {e!r} -- recording empty and moving on")
        data = None
    m = Measurement(row=row, column=column, electrochemical_test=test,
                    start_time=start_time, finish_time=dt.now(),
                    params=resolved, data=data)        # resolved params -> _meta.csv
    plate.measurements.append(m)
    write_measurement(m, plate.plate_id, root)
    return m


# ---- chosen tests on one cell ----
def run_cell(plate, row, column, tests=None, params_by_test=None, root="."):
    tests = ACTIVE_TESTS if tests is None else tests
    params_by_test = params_by_test or {}
    return [measure(plate, row, column, t, params_by_test.get(t), root) for t in tests]

# ====== Overnight CA calibration ======

def run_overnight_ca(cells=(0, 8, 16), voltage=1.0, time_run=4 * 3600,
                     sample_period=1.0, plate=None, root=".", stop_event=None):
    """Simultaneous CA, one cell per mux, recorded through the normal pipeline.
    Fresh CAL_* plate per call so reruns never overwrite. stop_event: optional
    threading.Event for early abort; collected data is still written."""
    if plate is None:
        plate = Plate(plate_id="CAL_" + dt.now().strftime("%Y%m%d_%H%M"),
                      config={"operator": "", "hypothesis": "overnight CA functionality",
                              "notes": f"dummy cells {list(cells)}"})
    record_sample(plate.plate_id, plate.created_at, plate.config.get("operator", ""),
                  plate.config.get("hypothesis", ""), plate.config.get("notes", ""), root)
    start = dt.now()
    dfs = run_ca_multi(cells, voltage=voltage, time_run=time_run,
                       sample_period=sample_period, stop_event=stop_event)
    finish = dt.now()
    for cell, df in dfs.items():
        row, col = cell // 4 + 1, "ABCD"[cell % 4]
        m = Measurement(row=row, column=col, electrochemical_test="CA",
                        start_time=start, finish_time=finish,
                        params={"voltage": voltage, "time_run": time_run,
                                "sample_period": sample_period, "hw_cell": cell},
                        data=df)
        plate.measurements.append(m)
        write_measurement(m, plate.plate_id, root)
    return plate


# ======= Testing =======
# Helpers to exercise the export path.

def createPlate(id=None, config_notes: dict = None) -> Plate:
    plate = Plate(
        plate_id=id or uuid.uuid4().hex,
        created_at=dt.now(),
        config=config_notes or {},  # FIX (cleanup): None crashed _resolve_params
    )
    print(f"Plate {plate.plate_id} has been created at {plate.created_at}")
    return plate

def plate_inputs():
    print("Following inputs are for PLATE LOG file (added to the plate_log.csv)")
    materialName = input("Material Name: ")
    catalystLoading = input("Catalyst Loading: ")
    nafionLoading = input("Nafion Loading: ")
    carbonBlackLoading = input("Carbon Black Loading: ")
    extractedData = input("Extracted Data: ")
    comments = input("Comments: ")
    return {
        "materialName" : materialName,
        "catalystLoading" : catalystLoading,
        "nafionLoading": nafionLoading,
        "carbonBlackLoading" : carbonBlackLoading,
        "extractedData" : extractedData,
        "comments" : comments,
    }

def run_test_cell(plate: Plate, row: int, column: str, plate_properties: dict = None, tests=None):
    """Run the active tests on one cell, then log the sample and plate-cell rows."""
    # logging.getLogger("toolkitpy").handlers.clear()
    logging.getLogger("toolkitpy").propagate = False
    if plate_properties is None:
        plate_properties = plate_inputs()                 # prompt if not supplied
    print(f"You are running Cell: {_resolve_cell(plate, row, column)}")
    measurements = run_cell(plate, row, column, tests=tests)   # tests=None -> ACTIVE_TESTS
    record_sample(plate.plate_id, plate.created_at, plate.config["operator"], plate.config["hypothesis"], plate.config["notes"])
    record_plate_cell(plate.plate_id, f"{row}{column}",
                      material_name=plate_properties["materialName"],
                      catalyst_loading=plate_properties["catalystLoading"],
                      nafion_loading=plate_properties["nafionLoading"],
                      carbon_black_loading=plate_properties["carbonBlackLoading"],
                      extracted_data=plate_properties["extractedData"],
                      comments=plate_properties["comments"])
    print(f"Test Complete -- {len(measurements)} measurements on cell {row}{column}")
    return measurements


if __name__ == "__main__":
    plate = createPlate(id="TEST01")
    run_test_cell(plate, row=1, column="A")   # plate_properties=None -> prompts

# Shell workflow (BatteryRobotUtils): rob.create_new_plate(), optionally
# rob.set_tests_list("PEIS", "CV"), then rob.run_tests_new(row, column).
# Plate-wide runs (Run All / Mux Cycle / FULL) go through the GUI: rob.new_plate().
# Overnight CA: plate = run_overnight_ca(cells=(0, 8, 16), voltage=1.0,
#               time_run=4*3600, sample_period=1.0)


# ---- MongoDB (Ciara_v2.cells: one doc per plate cell, runs.<test> per run) ----

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "Ciara_v2"
MONGO_COLLECTION = "cells"
MONGO_LIVE_UPLOAD = True            # False = record to disk only (testing)
 
_client = None
 
 
def _get_collection(uri=MONGO_URI, db_name=MONGO_DB, coll_name=MONGO_COLLECTION):
    """Lazy singleton; prints and returns None instead of raising. Non-blocking"""
    global _client
    try:
        if _client is None:
            from pymongo import MongoClient
            _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            _client.admin.command("ping")
        return _client[db_name][coll_name]
    except Exception as e:
        print("[mongo] connection failed ({}); skipping upload.".format(e))
        return None
 
 
def _mongo_safe(obj):
    """Coerce params into BSON-storable values (keys -> str, datetimes -> ISO)."""
    if isinstance(obj, dict):
        return {str(k): _mongo_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_mongo_safe(v) for v in obj]
    if isinstance(obj, dt):  # FIX (cleanup): from the deleted duplicate
        return obj.isoformat()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return str(obj)
 
def _fmt_time(t):
    """datetime or ISO string -> 'YYYY-MM-DD HH:MM:SS'."""
    try:
        if not isinstance(t, dt):
            t = dt.fromisoformat(str(t))
        return t.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(t)
    
def _log_row(path, keys):
    """Last row of a log csv matching all key columns; {} if absent/unreadable."""
    try:
        df = pd.read_csv(path, dtype=str).fillna("")
        for k, v in keys.items():
            df = df[df[k] == str(v)]
        return df.iloc[-1].to_dict() if len(df) else {}
    except Exception:
        return {}
 
 
def upload_cell_run(plate_id, cell_id, cell_num, test, params, time_ran, data_path,
                    data_df=None, upload=None):
    """Upsert one run under its cell document ($set runs.<test>; reruns overwrite).
    upload=None follows MONGO_LIVE_UPLOAD; pass False for local-only testing."""
    if not (MONGO_LIVE_UPLOAD if upload is None else upload):
        # keep this so we can test processes without spamming the mongoDB with stupid test runs
        return False
    coll = _get_collection()
    if coll is None:
        return False
    sample = _log_row(SAMPLE_LOG_DIRECTORY, {"plateID": plate_id})
    platelog = _log_row(PLATE_LOG_DIRECTORY, {"PlateID": plate_id, "Cell Position": cell_id})
    if data_df is None and data_path:
        try:
            data_df = pd.read_csv(data_path)
        except Exception:
            data_df = None
    run_doc = {
        "params": _mongo_safe(params),
        "time_ran": _fmt_time(time_ran),
        "path": str(data_path) if data_path else None,
        "analysis": analysis_subdoc(test, data_df, params) if data_df is not None else None,
    }
    try:
        coll.update_one({"_id": "{}_{}".format(plate_id, cell_id)}, {"$set": {
            "plate_id": plate_id, "cell": cell_id, "mux": cell_num // 8,
            "material_name": platelog.get("Material Name", ""),
            "hypothesis": sample.get("Hypothesis", ""),
            "notes": sample.get("Notes", ""),
            "runs.{}".format(test): run_doc,
            "last_upload": _fmt_time(dt.now()),
        }}, upsert=True)
    except Exception as e:
        print(f"[mongo] upsert failed {plate_id} {cell_id} {test}: {e!r}")
        return False
    return True
 
 
def backfill_plate_data(root=".", upload=True):
    """data/{plate}_{cell}/ folders written by write_measurement and upsert every
    run into Ciara_v2. Reruns just overwrite the same runs.<test> slots."""
    base = Path(root) / DATA_DIRECTORY
    n = 0
    for cell_dir in sorted(p for p in Path(base).iterdir() if p.is_dir()):
        plate_id, _, cell_id = cell_dir.name.rpartition("_")
        if not plate_id or not cell_id:
            continue
        try:
            r, c = int(cell_id[:-1]), cell_id[-1]
            cell_num = (r - 1) * 4 + ord(c.upper()) - ord("A")
        except Exception:
            cell_num = 0
        for meta_path in sorted(cell_dir.glob("*_meta.csv")):
            test = meta_path.name[len(cell_dir.name) + 1:-len("_meta.csv")]
            meta = {}
            try:
                mdf = pd.read_csv(meta_path, header=None, dtype=str).fillna("")
                if mdf.shape[1] >= 2:
                    meta = dict(zip(mdf[0], mdf[1]))
            except Exception:
                pass
            data_path = meta_path.with_name(meta_path.name.replace("_meta.csv", ".csv"))
            time_ran = meta.get("start_time", "") or meta.get("Start Time", "")
            if not time_ran and data_path.exists():
                time_ran = dt.fromtimestamp(os.path.getmtime(str(data_path))).strftime("%Y-%m-%d %H:%M:%S")
            params = {k: v for k, v in meta.items() if k not in ("plateID", "cellID", "test")}
            if upload_cell_run(plate_id, cell_id, cell_num, test, params, time_ran,
                               data_path if data_path.exists() else "", upload=upload):
                n += 1
    print("[backfill] uploaded {} runs into {}.{}".format(n, MONGO_DB, MONGO_COLLECTION))
    return n

# FULL-only protocol.
import math  # NOTE: BatteryRobotUtils uses math.* via `from triplet import *` -- keep
from datetime import timedelta
from utils.PStat import ca as _ca_driver

FULL_REVISIT_S = 60.0
FULL_VISIT_S = 0.1


def _full_runners():
    from importlib import import_module
    runners = {}
    for test, name in (("PEIS", "peis"), ("CV", "cv")):
        module = import_module("utils.PStat." + name)
        runner = getattr(module, "run_" + name + "_full", None)
        if not callable(runner):
            location = getattr(module, "__file__", name + ".py")
            raise RuntimeError(f"FULL runner missing from {location}. Replace utils/PStat/{name}.py "
                               "from the FULL package and restart the entire Python process.")
        runners[test] = runner
    if not callable(getattr(_ca_driver, "FullMuxSession", None)):
        raise RuntimeError("Replace utils/PStat/ca.py from the FULL package and restart Python.")
    return runners


def full_mux_groups(grid_cells):
    """{mux: [(row, col, hw), ...]} in channel order. FIX (cleanup): no cell_mapping."""
    groups = {}
    for hw in sorted({int(c) for c in grid_cells}):
        if not 0 <= hw < 24:
            raise ValueError("Grid cells must be integers from 0 to 23")
        groups.setdefault(hw // 8, []).append((hw // 4 + 1, "ABCD"[hw % 4], hw))
    if not groups:
        raise ValueError("No cells selected")
    return groups


def prepare_full_run(plate, grid_cells, root=".", tests=None):
    _full_runners()
    # FIX (FULL toggle): the dialog's Tests list is the FULL sequence --
    # PEIS/CV in any order (each optional, once), then CA
    tests = [canon_test(t) for t in (tests or ("PEIS", "CV", "CA"))]
    if (not tests or tests[-1] != "CA" or len(set(tests)) != len(tests)
            or any(t not in ("PEIS", "CV") for t in tests[:-1])):
        raise ValueError(f"FULL runs PEIS/CV (optional) then CA, each once; got {tests}")
    groups = full_mux_groups(grid_cells)
    params = {t: copy.deepcopy(_resolve_params(plate, t)) for t in ("PEIS", "CV", "CA")}
    voltage, period = float(params["CA"]["voltage"]), float(params["CA"]["sample_period"])
    duration = float(params["CA"]["time_run"])
    if not math.isfinite(voltage) or abs(voltage) > 4.9:
        raise ValueError("FULL local hold requires a finite CA voltage within +/-4.9 V")
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("CA hold (s) must be finite and above 0 s")
    if not math.isfinite(period) or not 0 < period <= duration:
        raise ValueError("CA sample_period must be positive and no greater than CA hold (s)")
    params["CA"].update(voltage=voltage, sample_period=period, time_run=duration)
    # FIX (CA_Back): revisit duration comes from the Mux Cycle dialog / MUX_CYCLE tab
    back = float(_resolve_params(plate, "MUX_CYCLE").get("ca_back_s", FULL_REVISIT_S))
    if not math.isfinite(back) or back < 0:
        raise ValueError("CA back (s) must be finite and 0 s or more (0 = no revisits)")
    params["CA"]["revisit_duration_s"] = back
    # FIX (CA_End): final all-cell cycle once a mux has finished every cell
    end = float(_resolve_params(plate, "MUX_CYCLE").get("ca_end_s", 0.0))
    if not math.isfinite(end) or end < 0:
        raise ValueError("CA end (s) must be finite and 0 s or more (0 = off)")
    params["CA"]["end_duration_s"] = end
    params["FULL_TESTS"] = list(tests)  # FIX (FULL toggle): read by run_full_mux
    print(f"[FULL] {', '.join(tests)} | CA hold {duration:g} s | CA_back {back:g} s | CA_end {end:g} s | "
          f"mux(es) {list(groups)}")  # FIX (CA_End): confirms what the lanes will use
    for cells in groups.values():
        for row, col, _ in cells:
            cell_id = f"{row}{col}"
            folder = Path(root) / DATA_DIRECTORY / _stem(plate.plate_id, cell_id)
            for test in tests:  # FIX (FULL toggle)
                path = folder / _data_filename(plate.plate_id, cell_id, test)
                if path.exists():
                    raise FileExistsError(f"FULL would overwrite {path}. Use a new plate ID or move that run first.")
    from utils.PStat.cv import _ensure_tkp
    _ensure_tkp("FULL")
    devices = _ca_driver._plate_devices()
    selected_muxes, selected_pstats = set(), set()
    for mi in groups:
        if mi >= len(devices[0]) or mi >= len(devices[1]):
            raise RuntimeError(f"Mux/pstat pair {mi} is unavailable")
        mux, pstat = devices[0][mi], devices[1][mi]
        if mux in selected_muxes or pstat in selected_pstats:
            raise RuntimeError(f"FULL mux {mi} would reuse a device assigned to another mux")
        selected_muxes.add(mux)
        selected_pstats.add(pstat)
    return groups, params, devices


class _FullCALog:
    columns = ["Point", "time", "Vf", "Im", "Cycle", "segment_id", "phase",
               "hw_cell", "mux", "channel", "datetime", "read_duration_s", "late_by_s"]

    def __init__(self, plate, position, params, root):
        self.plate, self.root = plate, root
        self.row, self.col, self.hw = position
        self.params = {**copy.deepcopy(params), "protocol": "FULL", "idle_mode": "local",
                       # FIX (CA_Back): record the duration actually used
                       "revisit_duration_s": float(params.get("revisit_duration_s", FULL_REVISIT_S)),
                       "visit_interval_s": FULL_VISIT_S,
                       "hw_cell": self.hw, "mux": self.hw // 8,
                       "time_basis": "seconds since this cell's initial CA acquisition",
                       "current_unit": "A", "charge_scope": "measured_segments_only"}
        self.rows = []
        self.origin = self.wall = None
        self.segment = 0
        self.last_time = -float("inf")
        self.measurement = None
        folder = Path(root) / DATA_DIRECTORY / _stem(plate.plate_id, f"{self.row}{self.col}")
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / _data_filename(plate.plate_id, f"{self.row}{self.col}", "CA")
        with self.path.open("x", newline="") as f:
            csv.DictWriter(f, self.columns).writeheader()

    def start(self, monotonic_time, wall_time):
        self.origin, self.wall = monotonic_time, wall_time

    def _row(self, elapsed, vf, im, phase, segment, cycle=0, read_s=0.0, late_s=0.0):
        if not all(math.isfinite(float(x)) for x in (elapsed, vf, im)):
            raise ValueError("Invalid CA time/voltage/current")
        if elapsed <= self.last_time:
            raise ValueError("CA timestamps must strictly increase")
        self.last_time = float(elapsed)
        return dict(zip(self.columns, [len(self.rows), float(elapsed), float(vf), float(im), cycle,
                    segment, phase, self.hw, self.hw // 8, self.hw % 8,
                    (self.wall + timedelta(seconds=float(elapsed))).isoformat(),
                    read_s, late_s]))

    def append_initial(self, df):
        names = {str(c).strip().lower(): c for c in df.columns}
        period = self.params["sample_period"]
        if "time" in names:
            times = pd.to_numeric(df[names["time"]], errors="raise").to_numpy()
        elif "time/s" in names:
            times = pd.to_numeric(df[names["time/s"]], errors="raise").to_numpy()
        elif "t" in names:
            times = pd.to_numeric(df[names["t"]], errors="raise").to_numpy()
        else:
            first = df.attrs.get("first_point", len(self.rows))
            times = [(first + i) * period for i in range(len(df))]
        if "stop_test" in names and (pd.to_numeric(df[names["stop_test"]]) != 0).any():
            self.params["instrument_stop"] = True
        new = []
        for elapsed, vf, im in zip(times, df[names["vf"]], df[names["im"]]):
            row = self._row(float(elapsed), vf, im, "initial", 0)
            self.rows.append(row)
            new.append(row)
        self._append(new)

    def append_revisit(self, timestamp, vf, im, cycle, read_s, late_s, phase="revisit"):  # FIX (CA_End): phase
        row = self._row(timestamp - self.origin, vf, im, phase, self.segment, cycle, read_s, late_s)
        self.rows.append(row)
        self._append([row])

    def _append(self, rows):
        if rows:
            with self.path.open("a", newline="") as f:
                csv.DictWriter(f, self.columns).writerows(rows)

    def finish(self, status):
        self.params["status"] = status
        self.params["initial_points"] = sum(r["phase"] == "initial" for r in self.rows)
        self.params["revisit_points"] = sum(r["phase"] == "revisit" for r in self.rows)  # FIX (CA_End): CA_back only
        self.params["end_points"] = sum(r["phase"] == "end" for r in self.rows)          # FIX (CA_End)
        self.params["late_visits"] = sum(r["late_by_s"] > 0 for r in self.rows)
        m = Measurement(self.row, self.col, "CA", start_time=self.wall or dt.now(), finish_time=dt.now(),
                        params=self.params, data=pd.DataFrame(self.rows, columns=self.columns))
        self.plate.measurements.append(m)
        self.measurement = m
        write_full_ca(m, self.plate.plate_id, self.root)
        return m


def run_full_mux(plate, mux_idx, positions, params, devices, root=".", stop_event=None,
                 fill=None, notify=None, sample_hook=None):
    """PEIS/CV/configured CA hold, then CA_Back s cycling (0.1 s per visit) over
    every finished cell on this mux, including the one that just finished.
    After the mux's last cell: CA_End s cycling over all of its cells."""
    stop_event = stop_event if stop_event is not None else threading.Event()
    positions = sorted(positions, key=lambda p: p[2])
    if any(hw // 8 != mux_idx for _, _, hw in positions):
        raise ValueError("FULL lane contains a cell from another mux")
    params = copy.deepcopy(params)
    initial_duration = float(params["CA"]["time_run"])
    back_s = float(params["CA"].get("revisit_duration_s", FULL_REVISIT_S))  # FIX (CA_Back)
    end_s = float(params["CA"].get("end_duration_s", 0.0))                  # FIX (CA_End)
    pre_tests = [t for t in params.get("FULL_TESTS", ("PEIS", "CV", "CA")) if t != "CA"]  # FIX (FULL toggle)
    runners = _full_runners()
    completed, logs, results = [], {}, []
    status = "complete"

    def report(pos, test, state, measurement=None, note=""):
        if notify:
            notify(pos[0], pos[1], test, state, measurement, note)

    def cycle_cells(session, cells, duration, label):
        """FIX (CA_End): one revisit pass (0.1 s per visit) over `cells` for
        `duration` s -- shared by CA_Back (label CA_REVISIT) and CA_End (CA_END).
        CA_End rows are written with phase "end", CA_Back rows with "revisit"."""
        phase = "end" if label == "CA_END" else "revisit"
        for prior in cells:
            logs[prior[2]].segment += 1
            report(prior, label, "running")

        def point(hw, timestamp, vf, im, visit, read_s, late_s):
            dest = logs[hw]
            if len(cells) > 1:
                dest.segment += 1
            dest.append_revisit(timestamp, vf, im, visit // len(cells), read_s, late_s, phase)
            if sample_hook:
                sample_hook(dest.row, dest.col, timestamp - dest.origin, im)

        session.revisit([p[2] for p in cells], duration, FULL_VISIT_S, stop_event, point)
        for prior in cells:
            report(prior, label, "stopped" if stop_event.is_set() else "complete")

    try:
        with _ca_driver.FullMuxSession(mux_idx, params["CA"]["voltage"], devices) as session:
            for pos in positions:
                row, col, hw = pos
                if stop_event.is_set():
                    break
                if fill is not None:
                    report(pos, "FILL", "running")
                    note = fill((row - 1) * 4 + "ABCD".index(col), stop_event.is_set)
                    if not note:
                        stop_event.set()
                        report(pos, "FILL", "stopped")
                        break
                    report(pos, "FILL", "complete", note=str(note))
                for test in pre_tests:  # FIX (FULL toggle): dialog order, was fixed PEIS, CV
                    if stop_event.is_set():
                        break
                    report(pos, test, "running")
                    started = dt.now()
                    name = f"{plate.plate_id}_{row}{col}_{test}"
                    if test == "PEIS":
                        data = runners["PEIS"](hw, output_file_name=name, parameter_list=copy.deepcopy(params[test]),
                                               hardware=session, stop_event=stop_event)
                    else:
                        p = params[test]
                        values = [copy.deepcopy(p[k]) for k in ("voltage_list", "scan_rates", "hold_times",
                                                               "maxcycle", "sample_period")]
                        data = runners["CV"](hw, output_file_name=name, values=values,
                                             hardware=session, stop_event=stop_event)
                    if data is None or data.empty:
                        if stop_event.is_set():
                            break
                        raise RuntimeError(f"{test} returned no data for {row}{col}")
                    if test == "PEIS" and "bad_value" in data and data["bad_value"].eq(1).all():
                        raise RuntimeError(f"PEIS returned no valid points for {row}{col}")
                    m = Measurement(row, col, test, started, dt.now(), copy.deepcopy(params[test]), data)
                    plate.measurements.append(m)
                    results.append(m)
                    write_measurement(m, plate.plate_id, root)
                    report(pos, test, "stopped" if stop_event.is_set() else "complete", m)
                if stop_event.is_set():
                    break
                report(pos, "CA", "running")
                log = _FullCALog(plate, pos, params["CA"], root)
                logs[hw] = log

                def initial_data(df, log=log, pos=pos):
                    log.append_initial(df)
                    if sample_hook and log.rows:
                        last = log.rows[-1]
                        sample_hook(pos[0], pos[1], last["time"], last["Im"])

                session.initial_ca(hw, initial_duration, params["CA"]["sample_period"],
                                   stop_event, log.start, initial_data)
                if stop_event.is_set():
                    break
                if log.params.get("instrument_stop"):
                    raise RuntimeError(f"CA instrument stop on {row}{col}")
                report(pos, "CA", "complete", note=f"{initial_duration:g} s complete; voltage hold")
                # FIX (CA_Back): the cell that just finished joins the revisit set
                # (A done, B just finished -> revisit A and B), for back_s seconds
                completed.append(pos)
                if back_s > 0:
                    cycle_cells(session, list(completed), back_s, "CA_REVISIT")
            # FIX (CA_End): every cell on this mux is done (tests + CA_Back) ->
            # keep cycling all of them for end_s seconds
            ids = ",".join(f"{r}{c}" for r, c, _ in completed)
            if end_s > 0 and completed and not stop_event.is_set():
                print(f"[FULL] mux{mux_idx}: CA_end start, {end_s:g} s over {ids}")
                cycle_cells(session, list(completed), end_s, "CA_END")
                print(f"[FULL] mux{mux_idx}: CA_end {'stopped' if stop_event.is_set() else 'done'}")
            else:
                print(f"[FULL] mux{mux_idx}: CA_end skipped (end_s={end_s:g}, cells done=[{ids}], "
                      f"stopped={stop_event.is_set()})")
    except BaseException:
        status = "failed"
        raise
    finally:
        if status != "failed" and stop_event.is_set():
            status = "stopped"
        errors = []
        for hw, log in logs.items():
            try:
                m = log.finish(status)
                results.append(m)
                report((log.row, log.col, hw), "CA_SAVED", status, m)
            except Exception as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError("FULL data finalization failed: " + "; ".join(map(str, errors)))
    return results



def write_full_ca(measurement, plate_id, root="."):
    cell_dir = Path(root) / DATA_DIRECTORY / _stem(plate_id, measurement.cell_id)
    cell_dir.mkdir(parents=True, exist_ok=True)
    stem = _stem(plate_id, measurement.cell_id)
    data_path = cell_dir / _data_filename(plate_id, measurement.cell_id, "CA")
    meta_path = cell_dir / _meta_filename(plate_id, measurement.cell_id, "CA")
    _atomic_csv(measurement.data, data_path)
    from utils.PStat.triplet_analysis import analyze_full_ca
    processed, analysis = analyze_full_ca(measurement.data)
    _atomic_csv(processed, cell_dir / (stem + "_FULL_CA_processed.csv"))
    _atomic_csv(pd.DataFrame([analysis]), cell_dir / (stem + "_FULL_CA_summary.csv"))
    fields = {"plateID": plate_id, "cell_id": measurement.cell_id, "row": measurement.row,
              "column": measurement.column, "cell_num": measurement.cell_num,
              "electrochemical_test": "CA", "start_time": measurement.start_time.isoformat(),
              "finish_time": measurement.finish_time.isoformat(), "n_points": len(measurement.data),
              **measurement.params, **analysis}
    with meta_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "value"])
        writer.writerows(fields.items())
    if MONGO_LIVE_UPLOAD:
        try:
            coll = _get_collection()
            if coll is not None:
                sample = _log_row(SAMPLE_LOG_DIRECTORY, {"plateID": plate_id})
                cell = _log_row(PLATE_LOG_DIRECTORY, {"PlateID": plate_id, "Cell Position": measurement.cell_id})
                coll.update_one({"_id": stem}, {"$set": {
                    "plate_id": plate_id, "cell": measurement.cell_id,
                    "mux": measurement.params["hw_cell"] // 8,
                    "material_name": cell.get("Material Name", ""),
                    "hypothesis": sample.get("Hypothesis", ""), "notes": sample.get("Notes", ""),
                    "runs.CA": {"params": _mongo_safe(measurement.params),
                                "time_ran": _fmt_time(measurement.start_time), "path": str(data_path),
                                "analysis": _mongo_safe(analysis)},
                    "last_upload": _fmt_time(dt.now()),
                }}, upsert=True)
        except Exception as exc:
            print(f"[mongo] FULL upsert failed {stem}: {exc!r}")
    return data_path, meta_path