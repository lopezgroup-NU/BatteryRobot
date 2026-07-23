# import csv
# import pandas as pd
# import uuid
# import json
# import shutil
# import re

# from __future__ import annotations
# from dataclasses import dataclass, field, asdict
# from datetime import datetime
# from pathlib import Path
# from typing import Any, Iterable

# from utils.PStat.peis import *
# from utils.PStat.cv import *
# from utils.PStat.ca import *

# import pandas as pd

# TEST_DIRECTORIES: dict[str, tuple[str, str]] = {
#     "geis": ("geis", "eis"),
#     "cv": ("cv", "cv")
# }

# @dataclass
# class StorageConfiguration:
#     res_root: str | Path = "C:\AttomRobotFiles\Data\DB_Missaka\Updated_Data_Sys\res"
#     res_summary_name: str = "data_summary.csv"

#     db_root: str | Path = "C:\AttomRobotFiles\Data\DB_Missaka\Updated_Data_Sys\db"
#     db_summary_name: str = "official_summary.csv"

#     mongo_url: str = "mongodb://localhost:27017/"
#     mongo_db: str = "test_db_zee_mk0" # NOTE: CHANGE LATER
#     mongo_collection: str = "new_system_data"

#     @property
#     def res_summary_path(self) -> Path:
#         return Path(self.res_root) / self.res_summary_name
    
#     @property
#     def db_summary_path(self) -> Path:
#         return Path(self.db_root) / self.db_summary_name
    
# DEFAULT_CONFIG = StorageConfiguration() # made to be mutatable, can change if paths change

# RES_SUMMARY_COLUMNS = [
#     "id",
#     "run_id",
#     "formulation",
#     "electrode",
#     "temp_C",
#     "created_at",
#     "notes",
#     "test_type",
#     "extra",    
# ]

# # 
# DB_SUMMARY_COLUMNS = [
#     "id",
#     "created_at",
#     "electrode",
#     "temp_C",
# ]


"""
    res folder  (all data from runs)
        -> data_summary.csv         one row per measurement, generated while running
    DB folder   (manual DB folder selection)
        -> official_summary.csv     rows fetched from data_summary by id
    Mongo       one document per formulation, holding the full record of each
                promoted measurement under its test_id

    Both summaries share one schema: the fixed COLUMNS below, followed by one
    dynamic column per component seen so far (arbitrary salts supported).
"""
from __future__ import annotations

import os
import re
import shutil
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import pandas as pd

# ---------------- file paths / config ----------------

MAIN_DIR = Path(r"C:\AttomRobotFiles\Software\BatteryRobot\MainProject\src\main")
DATA_SUMMARY = MAIN_DIR / "res" / "data_summary.csv"

DB_ROOT = Path(r"C:\AttomRobotFiles\Data\DB_Missaka")
OFFICIAL_SUMMARY = DB_ROOT / "official_summary.csv"

MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "G_updated"
MONGO_COLLECTION = "formulations"

# Fixed base columns; component columns follow dynamically.
COLUMNS = ["id", "formulation", "temp", "electrode", "date", "notes",
           "run_id", "run_type", "order", "path"]


# ---------------- formulation parsing ----------------

TAG_TOKENS = {"Pt", "GC", "GB"}          # never part of a component name
NOTE_TAGS = ("GC", "GB")                 # legacy tags routed to the notes column
NAME_ALIASES = {"CLO4": "ClO4",          # case variants seen in old filenames
                "LiSO4": "Li2SO4"}       # sulfate is 2-: typed LiSO4 -> Li2SO4

_CONC_RE = re.compile(r"^(?:(\d*)p(\d+)|(\d+))m?$")   # \d* : accepts p5 = 0.5
_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9()]*$")   # () for salts like Zn(OFT)2
_TEST_RE = re.compile(r"^(geis|cv)(\d*)$", re.IGNORECASE)
_DATE_RE = re.compile(r"^\d{8}$")
_TIME_RE = re.compile(r"^\d{6}$")


def _conc_value(token):
    m = _CONC_RE.match(token)
    if not m:
        return None
    if m.group(3) is not None:
        return float(m.group(3)) if token.endswith("m") else None   # bare int needs 'm'
    return float("{}.{}".format(m.group(1), m.group(2)))


def parse_formulation(s):
    """'TFSI_1p89m_SO4_0p1...' -> OrderedDict([('TFSI', 1.89), ('SO4', 0.1)]).
    Consecutive name tokens join until a concentration token closes the pair,
    so 'Acetate_pH_6p389m' -> {'Acetate_pH': 6.389}. {} for non-encoded names."""
    comps = OrderedDict()
    tokens = []
    for t in str(s).split("_"):                    # split fused pH tokens: pH4p6 -> pH, 4p6
        m = re.match(r"^[pP][hH]((?:\d|p\d).*)$", t)
        tokens.extend(["pH", m.group(1)] if m else [t])
    pending = []
    for t in tokens:
        t = NAME_ALIASES.get(t, t)
        v = _conc_value(t)
        if v is not None:
            if pending:
                comps["_".join(pending)] = v
            pending = []
        elif t in TAG_TOKENS:
            pending = []                           # electrode tag, never part of a name
        elif _NAME_RE.match(t) and t.lower() != "std":
            pending.append(t)
        else:
            pending = []                           # date/time/junk breaks a name chain
    return comps


def canonical_formulation(comps):
    return "_".join("{}_{}m".format(k, ("%g" % v).replace(".", "p")) for k, v in comps.items())


def _li_prefix(name):
    """Old tests all used Li cations: FSI -> LiFSI, SO4 -> Li2SO4.
    'pH' and Li* names untouched."""
    if name == "pH" or name.startswith("Li"):
        return name
    if name == "SO4":
        return "Li2SO4"
    return "Li" + name


def parse_legacy_stem(stem):
    """Legacy filename stem -> dict(formulation, components, run_type, order,
    electrode, date, run_id); None if not a legacy-encoded name."""
    note_tags, tokens = [], []
    for t in str(stem).split("_"):                 # route GC / GB (incl. fused GBNO3) to notes
        m2 = re.match(r"^(GC|GB)([A-Za-z].+)?$", t)
        if m2 and m2.group(1) in NOTE_TAGS and (m2.group(2) is None or _NAME_RE.match(m2.group(2))):
            if m2.group(1) not in note_tags:
                note_tags.append(m2.group(1))
            if m2.group(2):
                tokens.append(m2.group(2))
            continue
        tokens.append(t)
    m = _TEST_RE.match(tokens[-1])
    if not m:
        return None
    raw = parse_formulation("_".join(tokens))
    if not raw:
        return None
    comps = OrderedDict((_li_prefix(k), v) for k, v in raw.items())  # Li in columns too
    electrode, date_tok, time_tok = "", "", ""
    used = set()
    for k in raw:
        used.update(k.split("_"))
    for t in tokens[:-1]:
        if _DATE_RE.match(t):
            date_tok = t
        elif _TIME_RE.match(t):
            time_tok = t
        elif t.isalpha() and t not in used and t.lower() != "std" and not electrode:
            electrode = t
    date = ""
    if date_tok:
        hh, mm, ss = (time_tok[:2], time_tok[2:4], time_tok[4:]) if time_tok else ("00", "00", "00")
        date = "{}-{}-{} {}:{}:{}".format(date_tok[:4], date_tok[4:6], date_tok[6:], hh, mm, ss)
    form = canonical_formulation(comps)
    return {
        "formulation": form,
        "components": comps,
        "run_type": "GEIS" if m.group(1).lower() == "geis" else "CV",
        "order": int(m.group(2)) if m.group(2) else 0,
        "electrode": electrode,
        "date": date,
        "notes": " ".join(note_tags),
        # run key = formulation + session timestamp, so the 3 CV and 3 GEIS reps of
        # one visit share a run even when only CV names carry the electrode tag.
        # No timestamp in the stem -> fall back to the full prefix.
        "run_id": form + "|" + (date or "_".join(tokens[:-1])),
    }


# ---------------- dataclasses ----------------

@dataclass
class TestRecord:
    """One electrochemical measurement: one file in res, one row of data_summary."""
    id: str                 # per-measurement uuid hex
    run_id: str             # shared by the 6 measurements from each pump
    formulation: str        # Experiment column of the run csv
    run_type: str           # "GEIS" or "CV"
    order: int              # replicate 0-2
    electrode: str
    date: str               # required: a dropped date kwarg fails loudly, not blank
    temp: str = "NA"        # read back from the data file; "NA" if unreadable
    notes: str = ""
    path: str = ""          # absolute path of the data file this row points at
    components: dict = field(default_factory=dict)   # {salt: concentration}

    def to_row(self) -> dict:
        row = {c: getattr(self, c) for c in COLUMNS}
        row.update(self.components)
        return row


@dataclass
class FormulationDoc:
    """The Mongo unit: one formulation and the ids that belong to it."""
    formulation: str
    ids: List[dict] = field(default_factory=list)   # full record per test_id

    # replace-by-test_id: pull matching ids, then push fresh entries.
    # idempotent, and hand-edited fields (notes etc.) propagate on re-upload.
    def pull_update(self) -> dict:
        return {"$pull": {"ids": {"test_id": {"$in": [e["test_id"] for e in self.ids]}}}}

    def push_update(self) -> dict:
        return {
            "$push": {"ids": {"$each": self.ids}},
            "$set": {"formulation": self.formulation,
                     "last_upload": datetime.now().isoformat()},
        }


@dataclass
class SummaryCSV:
    """Wrapper for data_summary.csv / official_summary.csv.
    Schema = COLUMNS + dynamic component columns; every write is atomic
    (temp file + os.replace) so a crash can never leave a half-written file."""
    path: Path

    def _check_schema(self):
        if not self.path.exists():
            return
        with open(self.path, "r") as fh:
            first = fh.readline().strip()
        if first and first.split(",")[:len(COLUMNS)] != COLUMNS:
            raise RuntimeError(
                "{} does not start with the base schema in new_db.COLUMNS. "
                "Archive/rename the old file before writing new-format rows."
                .format(self.path))

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(columns=COLUMNS)
        return pd.read_csv(self.path, dtype=str).fillna("")

    def _atomic_write(self, df: pd.DataFrame):
        comp_cols = sorted(c for c in df.columns if c not in COLUMNS)
        df = df.reindex(columns=COLUMNS + comp_cols).fillna("")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        df.to_csv(tmp, index=False)
        os.replace(str(tmp), str(self.path))

    def _merge(self, df: pd.DataFrame, row: dict) -> pd.DataFrame:
        bad = [k for k in row if k not in COLUMNS and not re.match(r"^[A-Za-z][A-Za-z0-9_()]*$", str(k))]
        if bad:
            raise RuntimeError("Bad component column name(s): {}".format(bad))
        return pd.concat([df, pd.DataFrame([row])], ignore_index=True)

    def append(self, rec: "TestRecord"):
        self._check_schema()
        self._atomic_write(self._merge(self.load(), rec.to_row()))

    def append_rows(self, rows: List[dict]):
        self._check_schema()
        df = self.load()
        for row in rows:
            df = self._merge(df, row)
        self._atomic_write(df)

    def upsert(self, row: dict):
        """Insert or replace by id; base columns normalized, component columns pass through."""
        self._check_schema()
        base = {c: row.get(c, "") for c in COLUMNS}
        extras = {k: v for k, v in row.items() if k not in COLUMNS and str(v) != ""}
        row = dict(base, **extras)
        df = self.load()
        if not df.empty:
            df = df[df["id"] != row["id"]]
        self._atomic_write(self._merge(df, row))


# ---------------- helpers used by run_test ----------------

def read_temp(path) -> str:
    """same used in the BatteryRobotUtils file"""
    try:
        df = pd.read_csv(path, nrows=1)
        for c in df.columns:
            if "temp" in str(c).lower():
                v = df[c].iloc[0]
                return "NA" if pd.isna(v) else str(v)
    except Exception:
        pass
    return "NA"


def read_date(path) -> str:
    """datetime column the runner wrote into the data file; used by backfill too"""
    try:
        df = pd.read_csv(path, nrows=1)
        for c in df.columns:
            if "date" in str(c).lower() or "time" in str(c).lower():
                v = df[c].iloc[0]
                if not pd.isna(v):
                    return str(v)
    except Exception:
        pass
    return ""


def _file_mtime(path) -> str:
    """Last-resort date: the data file's modification time."""
    try:
        return datetime.fromtimestamp(os.path.getmtime(str(path))).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


# ---------------- legacy backfill: old folders -> summary csvs ----------------

def backfill_summary_from_folders(folders, summary=DATA_SUMMARY, electrode="Pt",
                                  link_to=None) -> pd.DataFrame:
    """Scan folder(s) of legacy csvs, parse each stem, and add one row per file
    not already in the summary (dedupe by path; id and run_id are fresh uuids,
    run_id shared by all files of one run key). Per-test date comes from the
    file itself (datetime column, then mtime), stem timestamp as last fallback.
    electrode: stem tag (Pt/GC/GB) when present, else the electrode default.
    link_to: path of another summary (e.g. data_summary when filling official);
    files whose name matches a row there reuse that row's id/run_id verbatim,
    so identifiers stay identical across both summaries and Mongo.
    Idempotent; unparseable names are reported and skipped. Returns added rows."""
    if isinstance(folders, (str, Path)):
        folders = [folders]
    csvfile = SummaryCSV(Path(summary))
    df_exist = csvfile.load()
    existing_paths = set(df_exist["path"]) if "path" in df_exist else set()
    run_ids = {}                                   # stem run key -> uuid run_id
    for pth, rid in zip(df_exist.get("path", []), df_exist.get("run_id", [])):
        m = parse_legacy_stem(Path(str(pth)).stem)
        if m:
            run_ids.setdefault(m["run_id"], rid)   # keeps grouping stable across reruns
    added, skipped, unknown, linked = [], 0, [], 0

    link = {}
    if link_to is not None and Path(link_to).exists():
        for _, lrow in SummaryCSV(Path(link_to)).load().iterrows():
            link[Path(str(lrow["path"])).name] = lrow.to_dict()

    files, fresh = [], []
    for folder in folders:
        files.extend(sorted(Path(folder).glob("*.csv")))
    for f in files:                                # pass 1: rows linked from link_to
        fpath = str(f.resolve())
        if fpath in existing_paths:
            skipped += 1
        elif f.name in link:
            row = dict(link[f.name])
            row["path"] = fpath
            m = parse_legacy_stem(f.stem)
            if m:                                  # seed run map so DB-only siblings join it
                run_ids.setdefault(m["run_id"], row["run_id"])
            added.append(row)
            existing_paths.add(fpath)
            linked += 1
        else:
            fresh.append(f)

    for f in fresh:                                # pass 2: files with no source row
            fpath = str(f.resolve())
            meta = parse_legacy_stem(f.stem)
            if meta is None:
                unknown.append(f.name)
                continue
            row = {
                "id": uuid.uuid4().hex,
                "formulation": meta["formulation"],
                "temp": read_temp(f),
                "electrode": meta["electrode"] or electrode or "",
                "date": read_date(f) or _file_mtime(f) or meta["date"],
                "notes": meta["notes"],
                "run_id": run_ids.setdefault(meta["run_id"], uuid.uuid4().hex),
                "run_type": meta["run_type"],
                "order": meta["order"],
                "path": fpath,
            }
            row.update(meta["components"])
            added.append(row)
            existing_paths.add(fpath)

    if added:
        csvfile.append_rows(added)
    print("[backfill] {} added ({} linked), {} already present, {} unparseable -> {}".format(
        len(added), linked, skipped, len(unknown), summary))
    for name in unknown:
        print("[backfill]   could not parse: {}".format(name))
    return pd.DataFrame(added)


def backfill_data_summary(folders=(MAIN_DIR / "res" / "geis", MAIN_DIR / "res" / "cv"),
                          summary=DATA_SUMMARY, electrode="Pt") -> pd.DataFrame:
    return backfill_summary_from_folders(folders, summary, electrode)


def backfill_official_summary(folders=(DB_ROOT / "eis", DB_ROOT / "cv"),
                              summary=OFFICIAL_SUMMARY, electrode="Pt",
                              link_to=DATA_SUMMARY) -> pd.DataFrame:
    return backfill_summary_from_folders(folders, summary, electrode, link_to)


# ---------------- typo repair: fix a mistyped Experiment after the fact ----------------

def fix_formulation(wrong, correct, summary=DATA_SUMMARY):
    """Repair rows whose Experiment was mistyped. `wrong` matches a formulation
    string or a single id; `correct` is the encoding as it should have been typed.
    Rewrites formulation + component columns, drops component columns left empty.
    Downstream artifacts are derived -- re-promote / re-upload / rebuild data.csv."""
    s = SummaryCSV(Path(summary))
    df = s.load()
    comps = parse_formulation(correct)
    form = canonical_formulation(comps) or str(correct)
    mask = (df["formulation"] == str(wrong)) | (df["id"] == str(wrong)) | (df["run_id"] == str(wrong))
    n = int(mask.sum())
    if n == 0:
        print("[fix] no rows match {!r} in {}".format(wrong, summary))
        return 0
    for c in [c for c in df.columns if c not in COLUMNS]:
        df.loc[mask, c] = ""
    df.loc[mask, "formulation"] = form
    for k, v in comps.items():
        if k not in df.columns:
            df[k] = ""
        df.loc[mask, k] = "%g" % v
    for c in [c for c in df.columns if c not in COLUMNS]:
        if (df[c].astype(str) == "").all():
            df = df.drop(columns=[c])
    s._atomic_write(df)
    print("[fix] {} rows -> {} in {}".format(n, form, summary))
    return n


# ---------------- manual selection: staging folder -> DB folder ----------------

def promote_folder(staging_dir,
                   data_summary=DATA_SUMMARY,
                   db_root=DB_ROOT,
                   official=OFFICIAL_SUMMARY,
                   move=False) -> pd.DataFrame:
    """
    Hand-copy the chosen data csvs from res into any folder; this takes that
    folder, looks each file's id up in data_summary.csv, copies the file into the
    DB folder (eis/ or cv/ by run_type), and upserts its row with the path
    rewritten to the DB copy. Component columns are carried through.

    Files whose stem is not in data_summary are reported and skipped.
    Re-upserting the same file is a no-op overwrite (idempotent).
    Set move=True to delete the staging copy after a successful promotion.
    Returns a DataFrame of the promoted rows.
    """
    staging = Path(staging_dir)
    src = SummaryCSV(Path(data_summary)).load()
    if src.empty:
        raise RuntimeError("No rows in {} -- nothing to look ids up in.".format(data_summary))

    official_csv = SummaryCSV(Path(official))
    promoted, unknown = [], []

    for f in sorted(staging.glob("*.csv")):
        rows = src[src["id"] == f.stem]                       # new-system files (uuid stem)
        if rows.empty:
            rows = src[src["id"] == f.stem.split("_")[0]]     # uuid ids with legacy '_eis' suffix
        if rows.empty:                                        # legacy files: match by filename
            rows = src[src["path"].apply(lambda p: Path(str(p)).name) == f.name]
        if rows.empty:
            unknown.append(f.name)
            continue
        row_src = rows.iloc[-1].to_dict()    # duplicate ids: last write wins
        row = dict(row_src)
        if not row.get("date", ""):          # backfill: legacy 'time' col -> file's datetime -> mtime
            row["date"] = row_src.get("time", "") or read_date(f) or _file_mtime(f)

        sub = "eis" if str(row.get("run_type", "")).upper() == "GEIS" else "cv"
        dest_dir = Path(db_root) / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / f.name
        shutil.copy2(str(f), str(dest))
        if move:
            f.unlink()

        row["path"] = str(dest)
        official_csv.upsert(row)
        promoted.append(row)

    print("[promote] {} promoted, {} unknown".format(len(promoted), len(unknown)))
    for name in unknown:
        print("[promote]   no data_summary row for: {}".format(name))
    return pd.DataFrame(promoted)


# ---------------- run aggregates: data.csv (one row per run) ----------------

DATA_CSV = MAIN_DIR / "data.csv"
CELL_CONSTANT = 6.06007673               # same constant as DBUtils.add_geis_data_one

RUN_FIELDS = ["run_id", "formulation", "water_weight", "precipitated_out",
              "avg_cv_diff", "cv_diff", "avg_highV", "highV", "avg_lowV", "lowV",
              "avg_cv_diff_rev", "cv_diff_rev", "avg_highV_rev", "highV_rev",
              "avg_lowV_rev", "lowV_rev", "ignore_first", "cv_date_uploaded",
              "temp(C)", "electrode_used", "paths", "valid_flag", "cv_error",
              "avg_conductivity", "conductivity", "geis_date_uploaded",
              "geis_error", "errors"]

_cv_interpret = None                     # injected lazily from DBUtils (reused as-is)
_water_weight = None


def _load_analysis():
    global _cv_interpret, _water_weight
    if _cv_interpret is None:
        from ..DBUtils import cv_interpret as _ci
        _cv_interpret = _ci
    if _water_weight is None:
        from ..MathUtils import get_water_weight_from_components as _gw
        _water_weight = _gw


def _base_salt(name):
    for pre in ("Li2", "Li"):
        if name.startswith(pre) and len(name) > len(pre):
            return name[len(pre):]
    return name


def _run_water_weight(components):
    try:
        old_style = {_base_salt(k): v for k, v in components.items()
                     if k != "pH" and not k.endswith("_pH")}
        return _water_weight(old_style)
    except Exception:
        return ""


def _geis_conductivity(path):
    df = pd.read_csv(path, index_col="# point")
    ok = df[df.reflected_zimag >= 0]
    zreal = ok["zreal"].loc[ok["reflected_zimag"].idxmin()]
    return CELL_CONSTANT / zreal


def _avg(vals, ignore_first):
    if not vals:
        return ""
    if ignore_first and len(vals) > 1:
        vals = vals[1:]
    return sum(vals) / len(vals)


def compute_run_aggregates(grp, comp_cols, ignore_first=True) -> dict:
    """data_summary/official rows of ONE run_id -> one data.csv-format record.
    Per-file failures are recorded in 'errors' and never abort the run."""
    try:
        _load_analysis()
    except Exception:
        pass
    errors = []
    parts = {}
    for rt in ("CV", "GEIS"):
        d = grp[grp["run_type"] == rt].copy()
        d["_o"] = pd.to_numeric(d["order"], errors="coerce")
        parts[rt] = d.sort_values("_o")
    cv, geis = parts["CV"], parts["GEIS"]

    diffs, highs, lows = [], [], []
    diffs_r, highs_r, lows_r = [], [], []
    for p in cv["path"]:
        try:
            df_, hf, lf = _cv_interpret(p, reverse_peak=False)
            dr, hr, lr = _cv_interpret(p, reverse_peak=True)
            diffs.append(df_); highs.append(hf); lows.append(lf)
            diffs_r.append(dr); highs_r.append(hr); lows_r.append(lr)
        except Exception as e:
            errors.append("cv {}: {}".format(Path(str(p)).name, e))
    conds = []
    for p in geis["path"]:
        try:
            conds.append(_geis_conductivity(p))
        except Exception as e:
            errors.append("geis {}: {}".format(Path(str(p)).name, e))

    first = grp.iloc[0]
    comps = {}
    for c in comp_cols:
        v = str(first.get(c, ""))
        if v != "":
            try:
                comps[c] = float(v)
            except Exception:
                comps[c] = v

    def _mtime_last(d):
        return _file_mtime(d["path"].iloc[-1]) if len(d) else ""

    rec = {
        "run_id": first["run_id"],
        "formulation": first["formulation"],
        "water_weight": _run_water_weight(comps),
        "precipitated_out": False,
        "avg_cv_diff": _avg(diffs, ignore_first), "cv_diff": diffs,
        "avg_highV": _avg(highs, ignore_first), "highV": highs,
        "avg_lowV": _avg(lows, ignore_first), "lowV": lows,
        "avg_cv_diff_rev": _avg(diffs_r, ignore_first), "cv_diff_rev": diffs_r,
        "avg_highV_rev": _avg(highs_r, ignore_first), "highV_rev": highs_r,
        "avg_lowV_rev": _avg(lows_r, ignore_first), "lowV_rev": lows_r,
        "ignore_first": ignore_first,
        "cv_date_uploaded": _mtime_last(cv),
        "temp(C)": next((t for t in grp["temp"] if str(t) not in ("", "NA")), ""),
        "electrode_used": next((e for e in grp["electrode"] if str(e) != ""), ""),
        "paths": [str(p) for p in grp["path"]],
        "valid_flag": not errors,
        "cv_error": diffs[2] - diffs[1] if len(diffs) == 3 else "",
        "avg_conductivity": _avg(conds, ignore_first), "conductivity": conds,
        "geis_date_uploaded": _mtime_last(geis),
        "geis_error": conds[2] - conds[1] if len(conds) == 3 else "",
        "errors": "; ".join(errors),
    }
    rec.update(comps)
    return rec


def build_data_csv(summary=DATA_SUMMARY, out=DATA_CSV, ignore_first=True) -> pd.DataFrame:
    """Rebuild data.csv from scratch: one row per run_id in the summary.
    Full-rebuild + atomic write = idempotent and crash-safe; a bad file or bad
    run is recorded in its row's errors/valid_flag, never aborts the build."""
    df = SummaryCSV(Path(summary)).load()
    if df.empty:
        raise RuntimeError("No rows in {}.".format(summary))
    comp_cols = [c for c in df.columns if c not in COLUMNS]
    recs, failed = [], 0
    for run_id, grp in df[df["run_id"] != ""].groupby("run_id", sort=False):
        try:
            recs.append(compute_run_aggregates(grp, comp_cols, ignore_first))
        except Exception as e:
            failed += 1
            recs.append({"run_id": run_id, "formulation": grp.iloc[0]["formulation"],
                         "valid_flag": False, "errors": "run failed: {}".format(e)})
    outdf = pd.DataFrame(recs)
    cols = RUN_FIELDS + sorted(c for c in outdf.columns if c not in RUN_FIELDS)
    outdf = outdf.reindex(columns=cols)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    outdf.to_csv(tmp, index=False)
    os.replace(str(tmp), str(out))
    bad = int((outdf["valid_flag"] != True).sum())
    print("[data.csv] {} runs written ({} with errors) -> {}".format(len(outdf), bad, out))
    return outdf


# ---------------- DB folder -> MongoDB ----------------

_client = None


def _get_collection(uri, db_name, coll_name):
    """Lazy singleton connection; prints and returns None instead of raising."""
    global _client
    try:
        if _client is None:                  # import only when actually constructing
            from pymongo import MongoClient
            _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            _client.admin.command("ping")
        return _client[db_name][coll_name]
    except Exception as e:
        print("[mongo] connection failed ({}); skipping upload.".format(e))
        return None


def _entry_from_row(r, comp_cols=()) -> dict:
    """Full official-summary row (Series) -> Mongo subdocument keyed by test_id.
    Label access, not attributes: itertuples mangles names like Zn(OFT)2."""
    try:
        order = int(float(r["order"]))
    except Exception:
        order = r["order"]
    comps = {}
    for c in comp_cols:
        v = str(r.get(c, ""))
        if v != "":
            try:
                comps[c] = float(v)
            except Exception:
                comps[c] = v
    return {
        "components": comps,
        "test_id": r["id"],
        "run_id": r["run_id"],
        "run_type": r["run_type"],
        "order": order,
        "electrode": r["electrode"],
        "temp": r["temp"],
        "date": r["date"],
        "notes": r["notes"],
        "path": r["path"],
    }


def upload_official_to_mongo(official=OFFICIAL_SUMMARY,
                             uri=MONGO_URI,
                             db_name=MONGO_DB,
                             coll_name=MONGO_COLLECTION,
                             include_runs=True) -> dict:
    """
    Read official_summary.csv and upsert into MongoDB, grouped by formulation:
    one document per formulation (_id = formulation string) whose 'ids' array
    holds the full record of each promoted measurement under its test_id.
    Replace-by-test_id ($pull then $push) keeps re-uploads idempotent and
    migrates older {test_id, run_id}-only entries in place. Pointer-only:
    paths, never data arrays.
    """
    path = Path(official)
    if not path.exists():
        raise RuntimeError("{} not found -- promote files first.".format(path))
    df = pd.read_csv(path, dtype=str).fillna("")
    if df.empty:
        print("[mongo] official summary is empty; nothing to upload.")
        return {"formulations": 0, "ids": 0, "status": "empty"}

    coll = _get_collection(uri, db_name, coll_name)
    if coll is None:
        return {"formulations": 0, "ids": 0, "status": "no-connection"}

    comp_cols = [c for c in df.columns if c not in COLUMNS]
    n_form = n_ids = n_runs = 0
    for formulation, grp in df.groupby("formulation", sort=True):
        doc = FormulationDoc(
            formulation=formulation,
            ids=[_entry_from_row(r, comp_cols) for _, r in grp.iterrows()])
        coll.update_one({"_id": formulation}, doc.pull_update())
        coll.update_one({"_id": formulation}, doc.push_update(), upsert=True)
        n_form += 1
        n_ids += len(doc.ids)
        if include_runs:
            run_docs = [compute_run_aggregates(g, comp_cols)
                        for _, g in grp[grp["run_id"] != ""].groupby("run_id", sort=False)]
            if run_docs:
                coll.update_one({"_id": formulation},
                    {"$pull": {"runs": {"run_id": {"$in": [d["run_id"] for d in run_docs]}}}})
                coll.update_one({"_id": formulation},
                    {"$push": {"runs": {"$each": run_docs}}}, upsert=True)
                n_runs += len(run_docs)

    print("[mongo] upserted {} formulation docs covering {} ids, {} runs".format(
        n_form, n_ids, n_runs))
    return {"formulations": n_form, "ids": n_ids, "runs": n_runs, "status": "ok"}