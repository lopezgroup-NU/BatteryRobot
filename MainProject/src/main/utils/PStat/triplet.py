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

import csv
import pandas as pd
import uuid
import base64
import copy

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
    with open(meta_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["field", "value"])
        w.writerows(rows)

    upload_cell_run(plate_id, measurement.cell_id, measurement.cell_num,
                    measurement.electrochemical_test, measurement.params,
                    measurement.start_time, data_path, data_df=measurement.data)

    return data_path, meta_path

# ts deprecated
def write_plate(plate, root: str | Path = ".", notes: str = "") -> None:
    """Write every measurement on a Plate and upsert its Sample Log row."""
    for m in plate.measurements:
        write_measurement(m, plate.plate_id, root)
    note_input = input("Notes for Sample Log (who, hypothesis, what): ")
    record_sample(plate.plate_id, plate.created_at, notes or plate.config.get("notes", "") or note_input, root)


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
        df = df[columns]
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

def choose_tests():
    """Interactive picker for the default test list."""
    avail = list(TEST_RUNNERS)
    print("Available:", ", ".join(f"[{i+1}] {t}" for i, t in enumerate(avail)))
    raw = input("Tests to run (names or numbers, space/comma separated): ").replace(",", " ").split()
    picked = []
    for tok in raw:
        if tok.isdigit() and 1 <= int(tok) <= len(avail):
            picked.append(avail[int(tok) - 1])
        elif tok.upper() in TEST_RUNNERS:
            picked.append(tok.upper())
        else:
            print(f"  ignoring unknown: {tok}")
    return set_tests(*picked) if picked else ACTIVE_TESTS


def all_cells() -> list[tuple[int, str]]:
    """Every cell on a 6x4 plate, as (row, column) pairs."""
    return [(r, c) for r in range(1, 7) for c in "ABCD"]



# Each runner: (cell, params, name) -> (DataFrame, resolved_params)
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
    "CA": {"voltage": 1.0, "time_run": 30, "sample_period": 0.1},
}

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
    """Hardware/MUX index for a plate position. Uses config['cell_mapping'] if present,
    else falls back to the row-major plate index."""
    mapping = plate.config.get("cell_mapping")
    if mapping is not None:
        return mapping[(row, column)]
    return (row - 1) * 4 + ord(column.upper()) - ord("A")

# ---- Things that actually make things run ---- #

TEST_RUNNERS = {"PEIS": _run_peis, "CV": _run_cv, "CA": _run_ca}

def measure(plate, row, column, test, params=None, root="."):
    """Run a single `test` on one cell, store it on `plate`, and write it to disk."""
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

def run_plate(plate, cells=None, tests=None, params_by_test=None, root="."):
    tests = ACTIVE_TESTS if tests is None else tests
    for (row, column) in (cells if cells is not None else all_cells()):
        run_cell(plate, row, column, tests, params_by_test, root)


# ====== Triplet ======
TRIPLET_TESTS = ["PEIS", "CV", "CA"] #specifically for the triplet stuff; SHOULD PROBABLY CHANGE INTO LIST

def run_triplet_cell(plate: Plate, row: int, column: str, root: str | Path = ".") -> list:
    """Run the full triplet (PEIS, CV, CA) on one cell."""
    return run_cell(plate, row, column, tests=TRIPLET_TESTS, root=root)

def run_triplet_plate(plate: Plate, root: str | Path = ".") -> None:
    """Run the full triplet on all 24 cells."""
    run_plate(plate, tests=TRIPLET_TESTS, root=root)


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

def make_short_uuid(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def createPlate(id=None, config_notes: dict = None) -> Plate:
    plate = Plate(
        plate_id=id or uuid.uuid4().hex,
        created_at=dt.now(),
        config=config_notes,
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

# NOTE: Must run rob.create_new_plate() first, 
# change the "DEFAULT_TESTS" to the tests you want to run (in sequential order)
# and then run rob.run_tests_new(row, column).
# There IS NO CODE FOR FULL PLATE RUNS, these are cell only.
# Overnight CA: plate = run_overnight_ca(cells=(0, 8, 16), voltage=1.0,
#               time_run=4*3600, sample_period=1.0)


# ---- MongoDB ----

from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"
MONGO_DB_NAME = "Ciara_v2"
PLATES_COLLECTION = "plates"
MEASUREMENTS_COLLECTION = "measurements"
class MongoConn:
    """Same shape as DBUtils.MongoConn, pointed at the triplet database."""
 
    def __init__(self, uri=MONGO_URI, db_name=MONGO_DB_NAME):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.connect()
 
    def connect(self):
        # if not _HAS_PYMONGO:
        #     raise RuntimeError("pymongo is not installed in this environment")
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]
 
    def get_collection(self, collection_name, db_name=None):
        if db_name:
            return self.client[db_name][collection_name]
        return self.db[collection_name]
 
 
_MONGO_CONN = None
 
def _get_conn() -> MongoConn:
    """One client per process (same idea as ensure_toolkit_init in pstat.py)."""
    global _MONGO_CONN
    if _MONGO_CONN is None:
        _MONGO_CONN = MongoConn()
    return _MONGO_CONN
 
 
def _mongo_safe(value):
    """Coerce params/config values into BSON-storable ones.
    Non-string dict keys (e.g. cell_mapping's (row, column) tuples) become str;
    datetimes become isoformat; all unknown falls back to str()."""
    if isinstance(value, dict):
        return {str(k): _mongo_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_mongo_safe(v) for v in value]
    if isinstance(value, dt):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
 
 
# ---- dataclass -> document ----
 
def measurement_doc(m: Measurement, plate_id: str, data_path=None, meta_path=None) -> dict:
    """key: value straight off the Measurement dataclass, plus file pointers.
    Mirrors the rows written to the _meta.csv."""
    return {
        "plate_id": plate_id,
        "cell_id": m.cell_id,
        "row": m.row,
        "column": m.column,
        "cell_num": m.cell_num,
        "electrochemical_test": m.electrochemical_test,
        "start_time": m.start_time.isoformat() if m.start_time else "",
        "finish_time": m.finish_time.isoformat() if m.finish_time else "",
        "n_points": 0 if m.data is None else len(m.data),
        "params": _mongo_safe(m.params),
        "data_path": str(data_path) if data_path else None,  # None = aborted/empty run
        "meta_path": str(meta_path) if meta_path else None,
    }
 
 
def plate_doc(plate: Plate) -> dict:
    """key: value off the Plate dataclass. Measurements live in their own
    collection; config carries operator/hypothesis/notes, so this doc is the
    Mongo equivalent of the sample_log row."""
    return {
        "plate_id": plate.plate_id,
        "created_at": plate.created_at.isoformat(),
        "config": _mongo_safe(plate.config or {}),
        "n_measurements": len(plate.measurements),
    }
 
 
def _measurement_paths(m: Measurement, plate_id: str, root: str | Path = "."):
    """Recreate the canonical paths write_measurement used. Returns None for
    files that don't exist on disk (e.g. no data CSV for an aborted run)."""
    cell_dir = Path(root) / DATA_DIRECTORY / _stem(plate_id, m.cell_id)
    data_path = cell_dir / _data_filename(plate_id, m.cell_id, m.electrochemical_test)
    meta_path = cell_dir / _meta_filename(plate_id, m.cell_id, m.electrochemical_test)
    return (data_path if data_path.exists() else None,
            meta_path if meta_path.exists() else None)
 
 
# ---- upserts ----
 
def db_index_measurement(m: Measurement, plate_id: str, root: str | Path = ".",
                         data_path=None, meta_path=None):
    """Upsert one pointer document. Never raises: an unreachable Mongo prints
    a warning instead of killing a hardware run."""
    if data_path is None and meta_path is None:
        data_path, meta_path = _measurement_paths(m, plate_id, root)
    doc = measurement_doc(m, plate_id, data_path, meta_path)
    key = {k: doc[k] for k in ("plate_id", "cell_id", "electrochemical_test", "start_time")}
    try:
        col = _get_conn().get_collection(MEASUREMENTS_COLLECTION)
        col.update_one(key, {"$set": doc}, upsert=True)
        return doc
    except Exception as e:
        print(f"[mongo] index failed for {plate_id} {m.cell_id} {m.electrochemical_test}: {e!r}")
        return None
 
 
def db_index_plate(plate: Plate, root: str | Path = "."):
    """Upsert the plate doc plus every measurement currently on the plate.
    Run after run_plate / run_triplet_plate to sync a whole run in one call."""
    try:
        col = _get_conn().get_collection(PLATES_COLLECTION)
        col.update_one({"plate_id": plate.plate_id}, {"$set": plate_doc(plate)}, upsert=True)
    except Exception as e:
        print(f"[mongo] plate index failed for {plate.plate_id}: {e!r}")
    n = 0
    for m in plate.measurements:
        if db_index_measurement(m, plate.plate_id, root) is not None:
            n += 1
    print(f"[mongo] indexed plate {plate.plate_id}: {n}/{len(plate.measurements)} measurements")
 
 
# ---- queries ----
 
def db_get_measurements(plate_id=None, cell_id=None, test=None) -> list:
    """Pointer docs matching whatever filters are given."""
    q = {}
    if plate_id:
        q["plate_id"] = plate_id
    if cell_id:
        q["cell_id"] = cell_id
    if test:
        q["electrochemical_test"] = test.upper()
    col = _get_conn().get_collection(MEASUREMENTS_COLLECTION)
    return list(col.find(q))
 
 
def db_load_data(doc) -> pd.DataFrame | None:
    """Follow a pointer document back to its data CSV."""
    p = doc.get("data_path")
    if not p or not Path(p).exists():
        return None
    return pd.read_csv(p)


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
    if isinstance(obj, dict):
        return {str(k): _mongo_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_mongo_safe(v) for v in obj]
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
    
def _zr_refl(df):
    if "freq" in df.columns:                     # guarantee high->low frequency order
        df = df.sort_values("freq", ascending=False)
    zr = pd.to_numeric(df["zreal"], errors="coerce")
    refl = -pd.to_numeric(df["zimag"], errors="coerce")
    ok = zr.notna() & refl.notna()
    return zr[ok].to_numpy(), refl[ok].to_numpy()

def x_intercept_nofit(df):
    """Legacy value (R1_nofit): zreal of the sample nearest the axis from above."""
    try:
        zr, refl = _zr_refl(df)
        m = refl >= 0
        if not m.any():
            return None
        return float(zr[m][np.argmin(refl[m])])
    except Exception:
        return None

def x_intercept(df, fit_points=4):
    try:
        zr, refl = _zr_refl(df)
        near = x_intercept_nofit(df)
        if near is None or len(zr) < 2:
            return near
        cross = np.where(np.diff(np.sign(refl)) != 0)[0]
        if len(cross):
            i = int(cross[0])
            zw, rw = zr[max(0, i - 1):i + 3], refl[max(0, i - 1):i + 3]
        else:
            apex = int(np.argmax(refl))          # no crossing: fit only the
            hf = np.arange(0, apex + 1)          # high-frequency branch, so a
            if len(hf) < 2:                      # low-freq touchdown near the axis
                return near                      # cannot masquerade as Rs
            sel = hf[np.argsort(refl[hf])[:max(2, fit_points)]]
            zw, rw = zr[sel], refl[sel]
        if len(zw) < 2 or np.ptp(rw) == 0:
            return near
        c, d = np.polyfit(rw, zw, 1)          # zreal = c*refl + d -> intercept = d
        span = max(np.ptp(zr), 1e-12)
        if not np.isfinite(d) or d < zr.min() - span or d > zr.max() + span:
            return near
        return float(d)
    except Exception:
        return None

 
 
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
        "x_intercept": x_intercept(data_df) if data_df is not None else None,
        "path": str(data_path) if data_path else None,
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