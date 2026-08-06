"""
triplet_analysis.py -- per-cell analysis + plots for the triplet plate system.
Ported from the reference activity workflow script: R_s from the positive-slope
PEIS x-intercept fit, CV cycle selection with optional iR/reference correction,
CA charge/O2 integration and extrema. Plots match the reference appearance.

Uses the matplotlib OO API only (no pyplot): safe from plate_gui worker threads.

analyze_cell_folder(cell_dir)        -> plots + CSVs into that folder
analyze_plate(data_root, plate_id)   -> all cells + combined CV overlay
analyze_all(data_root)               -> every plate in the root
CLI: python triplet_analysis.py <cell_folder> | <data_root> [plate_id]
"""

# NOTE: graphing disabled -- all plot generation is commented out below.
# Processed CSVs, extrema CSVs, and analysis summaries are still written.

from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
# from matplotlib.figure import Figure
# from matplotlib.backends.backend_agg import FigureCanvasAgg

FARADAY_C_PER_MOL = 96485.33212

# ======================================================
# Defaults (right from reference)
# ======================================================

ANALYSIS_DEFAULTS = {
    # --- PEIS / R_s fit ---
    "peis_min_fit_points": 3,
    "peis_max_fit_points": 6,
    "peis_min_positive_slope": 0.0,

    # --- CV ---
    "cv_cycle_number": 2,                    # ordinal: 2nd available cycle
    "cv_cycle_selection_mode": "ordinal",    # "ordinal" or "label"
    "cv_use_last_cycle_if_missing": True,
    "apply_ir_correction": True,
    "apply_reference_correction": False,
    "reference_value": None,                 # V; required only if ref correction ON
    "reference_value_mode": "rhe_crossing_vs_ref",  # or "ref_vs_rhe"
    "area_cm2": 1.0,
    "mass_g": 1.0,

    # --- CA ---
    "ca_threshold_mA": 0.05,
    "ca_charge_mode": "positive_only",       # "positive_only" | "raw" | "absolute"
    "ca_extrema_smoothing_window_points": 1,
    "ca_extrema_min_separation_s": 0.0,
    "ca_extrema_min_prominence_mA": 0.0,

    # --- CV plot (reference-style; None = auto bounds) ---
    "cv_plot_y": "geo",          # "geo" for mA/cm², "mass" for mA/g
    "cv_x_min": None,
    "cv_x_max": None,
    "cv_y_min": None,
    "cv_y_max": None,

    # --- output ---
    "dpi": 300,
}


def _resolve_analysis_params(params=None):
    out = dict(ANALYSIS_DEFAULTS)
    if params:
        out.update(params)
    return out


# ======================================================
# Column helpers (ported from the original script)
# ======================================================

def _norm_col(name):
    """Normalize a column name for forgiving matching."""
    s = str(name).lower()
    s = s.replace("\u00b5", "u").replace("\u03bc", "u").replace("\u2212", "-")
    return re.sub(r"[^a-z0-9]+", "", s)


def find_column(df, aliases, required=True):
    """Return the actual column name matching any alias (case/punctuation-insensitive)."""
    norm_to_actual = {_norm_col(c): c for c in df.columns}

    for alias in aliases:
        alias_norm = _norm_col(alias)
        if alias_norm in norm_to_actual:
            return norm_to_actual[alias_norm]

    for alias in aliases:
        alias_norm = _norm_col(alias)
        for col_norm, actual in norm_to_actual.items():
            if alias_norm and (alias_norm in col_norm or col_norm in alias_norm):
                return actual

    if required:
        raise KeyError(
            "Could not find a required column. Tried aliases: {}. Available columns: {}".format(
                aliases, list(df.columns)
            )
        )
    return None


def to_numeric(series):
    """Convert a column to numeric, tolerating decimal commas."""
    s = series.astype(str).str.strip().str.replace("\u2212", "-", regex=False)
    out_dot = pd.to_numeric(s, errors="coerce")
    out_comma = pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")
    if out_comma.notna().sum() > out_dot.notna().sum():
        return out_comma
    return out_dot


def current_to_mA(df, current_col):
    """Return current in mA. Gamry Im/Idc columns are in amps."""
    current = to_numeric(df[current_col])
    label = str(current_col).lower().replace("\u03bc", "u").replace("\u00b5", "u")
    norm_label = _norm_col(current_col)
    if norm_label in {"im", "idc"}:
        return current * 1000.0
    if "ua" in label or "/u" in label:
        return current / 1000.0
    if "/a" in label and "/ma" not in label:
        return current * 1000.0
    return current


def get_minus_imaginary_z(df):
    """Return -Im(Z) as numeric values. Gamry 'zimag' is Im(Z), so it is negated."""
    neg_im_col = find_column(
        df, ["-Im(Z)/Ohm", "-Im(Z)", "-Zim/Ohm", "-Z''/Ohm", "-Imag(Z)/Ohm"], required=False,
    )
    if neg_im_col is not None:
        return to_numeric(df[neg_im_col]), neg_im_col
    pos_im_col = find_column(
        df, ["Im(Z)/Ohm", "Im(Z)", "Zim/Ohm", "Z''/Ohm", "Imag(Z)/Ohm", "Zimag", "Zimag/Ohm", "Zim"],
        required=True,
    )
    return -to_numeric(df[pos_im_col]), pos_im_col


def safe_filename(name):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(name)).strip("_")
    return safe if safe else "sample"


def _load_triplet_csv(path):
    """Triplet CSVs are plain pandas exports: header on row 0, comma-delimited."""
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    keep = [c for c in df.columns if c and not c.lower().startswith("unnamed")]
    return df[keep].dropna(how="all").reset_index(drop=True)


def _save_fig(fig, path, dpi):
    # -- graphing disabled --
    # path = Path(path)
    # path.parent.mkdir(parents=True, exist_ok=True)
    # FigureCanvasAgg(fig)  # explicit attach: required on matplotlib < 3.6
    # fig.savefig(str(path), dpi=dpi, bbox_inches="tight")
    return None


# ======================================================
# PEIS: R_s from positive-slope x-intercept
# (algorithm ported unchanged; plotting now saves a PNG)
# ======================================================

def estimate_rs_from_positive_slope(
    re_z,
    minus_im,
    freq=None,
    sample_name="PEIS",
    min_fit_points=3,
    max_fit_points=6,
    min_positive_slope=0.0,
    plot_path=None,
    dpi=200,
):
    """
    Estimate solution resistance from the positive-slope high-frequency PEIS region.

    Method (identical to the original script):
      1. Order points high freq -> low freq when frequency is available,
         otherwise sort by Re(Z) ascending.
      2. Local Nyquist slopes d[-Im(Z)] / d[Re(Z)].
      3. First contiguous positive-slope region.
      4. Linear fit y = m*x + b on up to max_fit_points of that region.
      5. R_s = -b / m  (x-intercept).

    Returns (R_s, ordered_eis_df, fit_points_df, (m, b)).
    If plot_path is given, a diagnostic Nyquist PNG is written there.
    """
    eis = pd.DataFrame({
        "Re_Ohm": pd.Series(re_z, dtype="float64"),
        "minus_Im_Ohm": pd.Series(minus_im, dtype="float64"),
    })
    if freq is not None:
        eis["freq_Hz"] = pd.Series(freq, dtype="float64")

    keep_cols = ["Re_Ohm", "minus_Im_Ohm"] + (["freq_Hz"] if "freq_Hz" in eis.columns else [])
    eis = eis.replace([np.inf, -np.inf], np.nan).dropna(subset=keep_cols).copy()

    if len(eis) < 2:
        raise ValueError("Not enough valid PEIS points in {}".format(sample_name))

    if "freq_Hz" in eis.columns and eis["freq_Hz"].notna().sum() >= 2:
        eis = eis.sort_values("freq_Hz", ascending=False).reset_index(drop=True)
        order_note = "frequency-sorted high -> low"
    else:
        eis = eis.sort_values("Re_Ohm", ascending=True).reset_index(drop=True)
        order_note = "Re(Z)-sorted low -> high; no frequency column found"

    x = eis["Re_Ohm"].to_numpy(dtype=float)
    y = eis["minus_Im_Ohm"].to_numpy(dtype=float)

    dx = np.diff(x)
    dy = np.diff(y)
    slopes = np.divide(dy, dx, out=np.full_like(dy, np.nan, dtype=float), where=np.abs(dx) > 1e-15)

    positive_segment = np.isfinite(slopes) & (dx > 0) & (slopes > min_positive_slope)

    runs = []
    start = None
    for idx, is_positive in enumerate(positive_segment):
        if is_positive and start is None:
            start = idx
        elif (not is_positive) and start is not None:
            runs.append((start, idx - 1))
            start = None
    if start is not None:
        runs.append((start, len(positive_segment) - 1))

    def run_point_count(run):
        return run[1] - run[0] + 2  # n adjacent segments contain n+1 points

    chosen_run = None
    for run in runs:
        if run_point_count(run) >= min_fit_points:
            chosen_run = run
            break
    if chosen_run is None and runs:
        chosen_run = max(runs, key=run_point_count)

    positive_region_mask = np.zeros(len(eis), dtype=bool)
    if chosen_run is not None:
        positive_region_mask[chosen_run[0]:chosen_run[1] + 2] = True

    # ---------- fallback path: no positive-slope region ----------
    if chosen_run is None:
        crossing_indices = np.where(
            np.isfinite(y[:-1]) & np.isfinite(y[1:]) & (y[:-1] * y[1:] <= 0) & (y[:-1] != y[1:])
        )[0]
        if len(crossing_indices) > 0:
            idx = int(crossing_indices[0])
            R_s = x[idx] + (0 - y[idx]) * (x[idx + 1] - x[idx]) / (y[idx + 1] - y[idx])
            method_note = "fallback: interpolated zero crossing"
        else:
            idx = int(np.nanargmin(np.abs(y)))
            R_s = x[idx]
            method_note = "fallback: closest-to-zero -Im(Z) point"
        print("{} warning: no positive-slope PEIS region found; {}.".format(sample_name, method_note))

        # if plot_path is not None:
            # fig = Figure(figsize=(6, 6))
            # ax = fig.add_subplot(111)
            # ax.plot(x, y, marker="o", label="All PEIS data")
            # ax.axhline(0, linewidth=1)
            # ax.axvline(R_s, linestyle="--", label="R_s = {:.4g} Ω".format(R_s))
            # ax.scatter([R_s], [0], zorder=5, label="Resistance used")
            # ax.set_xlabel("Re(Z) / Ω")
            # ax.set_ylabel("-Im(Z) / Ω")
            # ax.set_title("{} PEIS resistance diagnostic".format(sample_name))
            # ax.legend()
            # ax.set_aspect("equal", adjustable="datalim")
            # ax.text(0.02, 0.98, method_note, transform=ax.transAxes, va="top")
            # _save_fig(fig, plot_path, dpi)

        return float(R_s), eis, pd.DataFrame(), (np.nan, np.nan)

    # ---------- normal path: fit the positive-slope region ----------
    fit_start, fit_end = chosen_run
    fit_idx = np.arange(fit_start, fit_end + 2)
    if len(fit_idx) > max_fit_points:
        fit_idx = fit_idx[:max_fit_points]

    fit_df = eis.iloc[fit_idx].copy()
    x_fit = fit_df["Re_Ohm"].to_numpy(dtype=float)
    y_fit = fit_df["minus_Im_Ohm"].to_numpy(dtype=float)

    if len(x_fit) < 2:
        raise ValueError("Could not select enough positive-slope PEIS points for {}.".format(sample_name))

    m, b = np.polyfit(x_fit, y_fit, 1)
    if not np.isfinite(m) or abs(m) < 1e-15:
        raise ValueError("Positive-slope PEIS fit for {} produced a near-zero/invalid slope.".format(sample_name))

    R_s = -b / m

    print(
        "{} PEIS R_s from positive-slope fit: {:.6g} ohm | fit y = {:.4g}x + {:.4g} "
        "| points used: {} | order: {}".format(sample_name, R_s, m, b, len(fit_df), order_note)
    )

    # if plot_path is not None:
        # fig = Figure(figsize=(6, 6))
        # ax = fig.add_subplot(111)
        # ax.plot(x, y, marker="o", label="All PEIS data")
        # if np.any(positive_region_mask):
            # ax.plot(x[positive_region_mask], y[positive_region_mask], marker="o",
                    # linestyle="None", label="selected positive-slope region")
        # ax.plot(x_fit, y_fit, marker="s", linestyle="None", label="points used for fit")

        # x_min = min(np.nanmin(x_fit), R_s)
        # x_max = max(np.nanmax(x_fit), R_s)
        # if np.isclose(x_min, x_max):
            # x_min -= 0.5
            # x_max += 0.5
        # x_line = np.linspace(x_min, x_max, 100)
        # ax.plot(x_line, m * x_line + b, label="fit: y={:.3g}x+{:.3g}".format(m, b))

        # ax.axhline(0, linewidth=1)
        # ax.axvline(R_s, linestyle="--", label="R_s = {:.4g} Ω".format(R_s))
        # ax.scatter([R_s], [0], zorder=5, label="x-intercept used")
        # ax.annotate("R_s = {:.4g} Ω".format(R_s), xy=(R_s, 0), xytext=(8, 12),
                    # textcoords="offset points", arrowprops=dict(arrowstyle="->"))
        # ax.set_xlabel("Re(Z) / Ω")
        # ax.set_ylabel("-Im(Z) / Ω")
        # ax.set_title("{} PEIS resistance diagnostic".format(sample_name))
        # ax.legend()
        # ax.set_aspect("equal", adjustable="datalim")
        # fig.tight_layout()
        # _save_fig(fig, plot_path, dpi)

    return float(R_s), eis, fit_df, (float(m), float(b))


def analyze_peis_csv(peis_csv, sample_name, plot_path, p):
    """Load a triplet PEIS CSV, estimate R_s, save the Nyquist diagnostic PNG."""
    df = _load_triplet_csv(peis_csv)

    re_col = find_column(df, ["Re(Z)/Ohm", "Re(Z)", "Zre/Ohm", "Z'/Ohm", "Zreal/Ohm", "Zreal", "Zre"])
    minus_im, im_col = get_minus_imaginary_z(df)
    freq_col = find_column(df, ["freq/Hz", "freq", "Freq", "frequency/Hz", "Frequency/Hz", "f/Hz"], required=False)

    re_z = to_numeric(df[re_col])
    freq = to_numeric(df[freq_col]) if freq_col is not None else None

    R_s, ordered, fit_points, (m, b) = estimate_rs_from_positive_slope(
        re_z, minus_im,
        freq=freq,
        sample_name=sample_name,
        min_fit_points=int(p["peis_min_fit_points"]),
        max_fit_points=int(p["peis_max_fit_points"]),
        min_positive_slope=float(p["peis_min_positive_slope"]),
        plot_path=plot_path,
        dpi=int(p["dpi"]),
    )

    return {
        "R_s_ohm": R_s,
        "R_s_method": "positive_slope_x_intercept",
        "PEIS_fit_slope": m,
        "PEIS_fit_intercept": b,
        "PEIS_fit_points": int(len(fit_points)),
        "PEIS_valid_points": int(len(ordered)),
        "PEIS_file": str(peis_csv),
        "PEIS_nyquist_png": str(plot_path),
    }


# ======================================================
# CV: cycle selection + optional iR / reference correction
# ======================================================

def _format_cycle_label(value):
    try:
        value_f = float(value)
        if np.isfinite(value_f) and value_f.is_integer():
            return int(value_f)
        return value_f
    except Exception:
        return value


def _select_requested_cv_cycle(processed, cycle_number, sample_name, mode, use_last_if_missing):
    """Select the requested CV cycle. Ordinal mode: cycle_number = Nth available cycle."""
    mode = str(mode).strip().lower()
    cycle_numeric = to_numeric(processed["cycle"])
    valid_cycle_labels = sorted(pd.unique(cycle_numeric.dropna()))
    available = [_format_cycle_label(v) for v in valid_cycle_labels]

    if len(valid_cycle_labels) == 0:
        print("No valid numeric cycle labels found for {}; using the full CV file.".format(sample_name))
        return processed.copy(), np.nan, "full_file_no_valid_cycle_labels", available

    if mode in {"ordinal", "order", "nth", "1-based", "one_based"}:
        requested_index = int(cycle_number) - 1
        if requested_index < 0:
            raise ValueError("cv_cycle_number must be >= 1 in ordinal mode.")
        if requested_index >= len(valid_cycle_labels):
            if use_last_if_missing:
                requested_index = len(valid_cycle_labels) - 1
                actual_label = valid_cycle_labels[requested_index]
                print(
                    "Requested ordinal CV cycle {} for {}, but only {} cycle(s) found. "
                    "Using last available cycle label {}. Available: {}".format(
                        cycle_number, sample_name, len(valid_cycle_labels),
                        _format_cycle_label(actual_label), available)
                )
            else:
                raise ValueError(
                    "Requested ordinal CV cycle {} for {}, but only {} cycle(s) found. "
                    "Available cycle labels: {}".format(cycle_number, sample_name,
                                                       len(valid_cycle_labels), available)
                )
        else:
            actual_label = valid_cycle_labels[requested_index]
            if _format_cycle_label(actual_label) != int(cycle_number):
                print(
                    "{}: requested ordinal CV cycle {}; using actual file cycle label {}. "
                    "Available: {}".format(sample_name, cycle_number,
                                           _format_cycle_label(actual_label), available)
                )
        selected = processed[np.isclose(cycle_numeric, actual_label, equal_nan=False)].copy()
        selection_mode_used = "ordinal"

    elif mode in {"label", "exact", "cycle_label"}:
        actual_label = float(cycle_number)
        selected = processed[np.isclose(cycle_numeric, actual_label, equal_nan=False)].copy()
        selection_mode_used = "label"
        if selected.empty:
            raise ValueError(
                "Cycle label {} not found for {}. Available cycle labels: {}".format(
                    cycle_number, sample_name, available)
            )
    else:
        raise ValueError("cv_cycle_selection_mode must be 'ordinal' or 'label'; got {!r}".format(mode))

    if selected.empty:
        raise ValueError(
            "No CV points remained after selecting cycle {} for {}. Available: {}".format(
                cycle_number, sample_name, available)
        )
    return selected, _format_cycle_label(actual_label), selection_mode_used, available


def process_cv_csv(cv_csv, R_s, sample_name, out_csv, plot_path, p):
    """
    Load one triplet CV CSV, apply the optional corrections, select the requested
    cycle, write the processed CSV, and save the per-cell CV plot.

    R_s may be None/NaN: iR correction is then skipped and flagged in the output.
    Returns (processed_cycle_df, summary_dict).
    """
    df = _load_triplet_csv(cv_csv)

    ewe_col = find_column(df, ["Ewe/V", "<Ewe>/V", "Ewe", "Ewe/V vs. Ref.", "Ewe-Ece/V", "Vf", "Vf/V", "Vm"])
    current_col = find_column(df, ["<I>/mA", "I/mA", "I/A", "<I>/A", "I/uA", "Im", "Im/A", "I"])
    cycle_col = find_column(df, ["cycle number", "cycle", "Cycle", "cycle_number", "loop number"], required=False)
    time_col = find_column(df, ["time/s", "time", "t/s", "T", "Time [s]", "Time [Sec]", "time/sec"], required=False)

    ewe_v = to_numeric(df[ewe_col])
    current_mA = current_to_mA(df, current_col)
    cycle_values = to_numeric(df[cycle_col]) if cycle_col is not None else pd.Series(np.nan, index=df.index)
    time_s = to_numeric(df[time_col]) if time_col is not None else pd.Series(np.nan, index=df.index)

    apply_ref = bool(p["apply_reference_correction"])
    apply_ir = bool(p["apply_ir_correction"]) and R_s is not None and np.isfinite(R_s)
    ir_skipped_no_rs = bool(p["apply_ir_correction"]) and not apply_ir

    R_s_for_calc = float(R_s) if apply_ir else 0.0
    iR_drop_V = (current_mA / 1000.0) * (float(R_s) if (R_s is not None and np.isfinite(R_s)) else np.nan)
    iR_drop_applied_V = (current_mA / 1000.0) * R_s_for_calc if apply_ir else pd.Series(0.0, index=df.index)

    ref_value = p.get("reference_value")
    mode = str(p["reference_value_mode"]).strip().lower()

    if apply_ref:
        if ref_value is None or pd.isna(ref_value):
            raise ValueError(
                "Reference correction is ON but no reference_value was provided for {}.".format(sample_name)
            )
        if mode in {"rhe_crossing_vs_ref", "rhe_vs_ref", "calibration_crossing", "zero_crossing_vs_ref"}:
            reference_corrected_v = ewe_v - float(ref_value)
        elif mode in {"ref_vs_rhe", "reference_vs_rhe", "eref_vs_rhe"}:
            reference_corrected_v = ewe_v + float(ref_value)
        else:
            raise ValueError("reference_value_mode must be 'rhe_crossing_vs_ref' or 'ref_vs_rhe'.")
    else:
        reference_corrected_v = ewe_v.copy()

    processed_potential_v = reference_corrected_v - iR_drop_applied_V

    if apply_ref and apply_ir:
        correction_description = "reference + iR corrected"
        processed_axis_label = "iR-corrected potential (V vs RHE)"
    elif apply_ref:
        correction_description = "reference corrected only"
        processed_axis_label = "Potential (V vs RHE)"
    elif apply_ir:
        correction_description = "iR corrected only; no reference correction"
        processed_axis_label = "iR-corrected potential (V vs reference)"
    else:
        correction_description = "raw potential; no reference or iR correction"
        processed_axis_label = "Raw potential (V vs reference)"
    if ir_skipped_no_rs:
        correction_description += " (iR requested but no valid R_s available)"

    area = float(p["area_cm2"])
    mass = float(p["mass_g"])

    processed = pd.DataFrame({
        "sample_name": sample_name,
        "source_file": Path(cv_csv).name,
        "time_s": time_s,
        "cycle": cycle_values,
        "Ewe_raw_V": ewe_v,
        "current_mA": current_mA,
        "iR_drop_V": iR_drop_V,
        "iR_drop_applied_V": iR_drop_applied_V,
        "Reference_Corrected_E_V": reference_corrected_v,
        "Processed_E_V": processed_potential_v,
        "GeoNorm_mA_cm2": current_mA / area,
        "MassNorm_mA_g": current_mA / mass,
        "R_s_ohm": R_s if R_s is not None else np.nan,
        "APPLY_REFERENCE_CORRECTION": apply_ref,
        "APPLY_IR_CORRECTION": apply_ir,
        "correction_description": correction_description,
        "processed_axis_label": processed_axis_label,
        "area_cm2": area,
        "mass_g": mass,
    })
    processed = processed.dropna(subset=["Processed_E_V", "current_mA"]).reset_index(drop=True)
    if processed.empty:
        raise ValueError("no valid CV points in {} (aborted/empty run?)".format(Path(cv_csv).name))

    if cycle_col is not None:
        selected, actual_label, selection_mode_used, available = _select_requested_cv_cycle(
            processed, p["cv_cycle_number"], sample_name,
            p["cv_cycle_selection_mode"], p["cv_use_last_cycle_if_missing"],
        )
    else:
        print("No cycle-number column found for {}; using the full CV file.".format(sample_name))
        selected = processed.copy()
        actual_label = np.nan
        selection_mode_used = "full_file_no_cycle_column"
        available = []

    selected = selected.copy()
    selected["CV_cycle_requested"] = p["cv_cycle_number"]
    selected["CV_cycle_label_used"] = actual_label
    selected["CV_cycle_selection_mode"] = selection_mode_used
    selected["CV_available_cycle_labels"] = ";".join(map(str, available))

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(out_csv, index=False)

    if str(p["cv_plot_y"]).strip().lower() in {"mass", "massnorm", "mass_normalized"}:
        y_col, y_label = "MassNorm_mA_g", "Mass normalized current (mA/g)"
    else:
        y_col, y_label = "GeoNorm_mA_cm2", "Geometric normalized current (mA/cm²)"
    correction_text = "ref ON" if apply_ref else "ref OFF"
    correction_text += ", iR ON" if apply_ir else ", iR OFF"

    # fig = Figure(figsize=(8, 6))
    # ax = fig.add_subplot(111)
    # ax.plot(selected["Processed_E_V"], selected[y_col], label=str(sample_name), linewidth=2)
    # ax.set_xlabel(processed_axis_label)
    # ax.set_ylabel(y_label)
    # ax.set_title("Processed CV overlay, requested cycle {} ({} mode; {})".format(
        # p["cv_cycle_number"], p["cv_cycle_selection_mode"], correction_text))
    # if p["cv_x_min"] is not None or p["cv_x_max"] is not None:
        # ax.set_xlim(left=p["cv_x_min"], right=p["cv_x_max"])
    # if p["cv_y_min"] is not None or p["cv_y_max"] is not None:
        # ax.set_ylim(bottom=p["cv_y_min"], top=p["cv_y_max"])
    # ax.legend()
    # fig.tight_layout()
    # _save_fig(fig, plot_path, int(p["dpi"]))

    summary = {
        "CV_file": str(cv_csv),
        "CV_processed_csv": str(out_csv),
        "CV_plot_png": str(plot_path),
        "CV_processed_points": int(len(selected)),
        "CV_cycle_requested": p["cv_cycle_number"],
        "CV_cycle_label_used": actual_label,
        "CV_cycle_selection_mode": selection_mode_used,
        "CV_available_cycle_labels": ";".join(map(str, available)),
        "APPLY_REFERENCE_CORRECTION": apply_ref,
        "APPLY_IR_CORRECTION": apply_ir,
        "CV_correction_description": correction_description,
    }
    return selected, summary


# ======================================================
# CA: charge / O2 integration + extrema (ported)
# ======================================================

def cumulative_trapezoid_np(y, x):
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    if len(y) == 0:
        return np.array([], dtype=float)
    if len(y) == 1:
        return np.array([0.0], dtype=float)
    dx = np.diff(x)
    avg_y = 0.5 * (y[:-1] + y[1:])
    d_area = avg_y * dx
    d_area = np.where(np.isfinite(d_area) & np.isfinite(dx) & (dx >= 0), d_area, 0.0)
    return np.r_[0.0, np.cumsum(d_area)]


def current_for_charge(current_mA, mode="positive_only"):
    current_A = np.asarray(current_mA, dtype=float) / 1000.0
    mode = str(mode).strip().lower()
    if mode == "positive_only":
        return np.clip(current_A, 0, None)
    if mode == "raw":
        return current_A
    if mode == "absolute":
        return np.abs(current_A)
    raise ValueError("CA charge mode must be 'positive_only', 'raw', or 'absolute'.")


def first_downward_threshold_crossing(time_s, current_mA, threshold_mA=0.05):
    t = np.asarray(time_s, dtype=float)
    i = np.asarray(current_mA, dtype=float)
    valid = np.isfinite(t) & np.isfinite(i)
    t = t[valid]
    i = i[valid]
    if len(t) == 0:
        return np.nan
    order = np.argsort(t)
    t = t[order]
    i = i[order]
    if i[0] < threshold_mA:
        return float(t[0])
    for n in range(1, len(t)):
        i0, i1 = i[n - 1], i[n]
        if i0 >= threshold_mA and i1 < threshold_mA:
            if np.isclose(i1, i0):
                return float(t[n])
            frac = (threshold_mA - i0) / (i1 - i0)
            return float(t[n - 1] + frac * (t[n] - t[n - 1]))
    return np.nan


def _smooth_current_for_extrema(current_mA, smoothing_window_points=1):
    window = max(int(smoothing_window_points) if smoothing_window_points else 1, 1)
    return (
        pd.Series(current_mA, dtype="float64")
        .rolling(window=window, center=True, min_periods=1)
        .mean()
        .to_numpy()
    )


def _fill_zero_derivative_signs(sign):
    sign = np.asarray(sign, dtype=float).copy()
    if len(sign) == 0:
        return sign
    for j in range(1, len(sign)):
        if sign[j] == 0 and sign[j - 1] != 0:
            sign[j] = sign[j - 1]
    for j in range(len(sign) - 2, -1, -1):
        if sign[j] == 0 and sign[j + 1] != 0:
            sign[j] = sign[j + 1]
    return sign


_EXTREMA_COLS = ["extremum_type", "time_s", "time_min", "current_mA", "smoothed_current_mA", "index"]


def find_ca_extrema(time_s, current_mA, smoothing_window_points=1,
                    min_separation_s=0.0, min_prominence_mA=0.0):
    df = pd.DataFrame({"time_s": time_s, "current_mA": current_mA})
    df = df.dropna(subset=["time_s", "current_mA"]).sort_values("time_s").reset_index(drop=True)
    if len(df) < 3:
        return pd.DataFrame(columns=_EXTREMA_COLS)

    t = df["time_s"].to_numpy(dtype=float)
    i_raw = df["current_mA"].to_numpy(dtype=float)
    i_smooth = _smooth_current_for_extrema(i_raw, smoothing_window_points)

    dy = np.diff(i_smooth)
    sign = _fill_zero_derivative_signs(np.sign(dy))
    turn = np.diff(sign)
    maxima_idx = np.where(turn < 0)[0] + 1
    minima_idx = np.where(turn > 0)[0] + 1

    rows = []
    for kind, idx_arr in (("maximum", maxima_idx), ("minimum", minima_idx)):
        for idx in idx_arr:
            if idx <= 0 or idx >= len(df) - 1:
                continue
            if kind == "maximum":
                local_prominence = min(i_smooth[idx] - i_smooth[idx - 1], i_smooth[idx] - i_smooth[idx + 1])
            else:
                local_prominence = min(i_smooth[idx - 1] - i_smooth[idx], i_smooth[idx + 1] - i_smooth[idx])
            if local_prominence < min_prominence_mA:
                continue
            rows.append({
                "extremum_type": kind,
                "time_s": float(t[idx]),
                "time_min": float(t[idx] / 60.0),
                "current_mA": float(i_raw[idx]),
                "smoothed_current_mA": float(i_smooth[idx]),
                "index": int(idx),
            })

    extrema = pd.DataFrame(rows)
    if extrema.empty:
        return pd.DataFrame(columns=_EXTREMA_COLS)
    extrema = extrema.sort_values("time_s").reset_index(drop=True)

    min_separation_s = float(min_separation_s or 0.0)
    if min_separation_s > 0:
        kept, last_kept = [], -np.inf
        for _, row in extrema.iterrows():
            if row["time_s"] - last_kept >= min_separation_s:
                kept.append(row)
                last_kept = row["time_s"]
        extrema = pd.DataFrame(kept).reset_index(drop=True)
    return extrema


def _ca_time_series(df, ca_csv, sample_name):
    """Return the CA time axis in seconds; synthesize from meta sample_period if absent."""
    time_col = find_column(df, ["time/s", "time", "t/s", "T", "Time [s]", "Time [Sec]", "time/sec"],
                           required=False)
    if time_col is not None:
        return to_numeric(df[time_col]), "column:{}".format(time_col)

    # No time column: try the companion meta CSV for the sample period.
    period = None
    meta_path = Path(str(ca_csv).replace(".csv", "_meta.csv"))
    if meta_path.exists():
        try:
            meta = pd.read_csv(meta_path)
            kv = dict(zip(meta.iloc[:, 0].astype(str), meta.iloc[:, 1]))
            for key in ("sample_period", "sample_time", "sample_rate"):
                if key in kv:
                    period = float(kv[key])
                    break
        except Exception:
            period = None
    if period is None or not np.isfinite(period) or period <= 0:
        period = 0.1
        print("{} warning: no CA time column and no sample_period in meta; assuming 0.1 s.".format(sample_name))
    return pd.Series(np.arange(len(df), dtype=float) * period, index=df.index), \
        "synthesized ({} s/pt)".format(period)


def analyze_ca_csv(ca_csv, sample_name, out_prefix, p):
    """Load a triplet CA CSV; integrate charge/O2, find extrema; save 2 PNGs + 2 CSVs."""
    df = _load_triplet_csv(ca_csv)

    current_col = find_column(df, ["<I>/mA", "I/mA", "I/A", "<I>/A", "I/uA", "Im", "Im/A", "I"])
    ewe_col = find_column(df, ["Ewe/V", "<Ewe>/V", "Ewe", "Vf", "Vf/V", "Vm"], required=False)
    time_s, time_source = _ca_time_series(df, ca_csv, sample_name)

    current_mA = current_to_mA(df, current_col)
    ewe_v = to_numeric(df[ewe_col]) if ewe_col is not None else pd.Series(np.nan, index=df.index)

    ca = pd.DataFrame({
        "sample_name": sample_name,
        "source_file": Path(ca_csv).name,
        "time_s": time_s,
        "time_min": time_s / 60.0,
        "current_mA": current_mA,
        "Ewe_V": ewe_v,
    })
    ca = ca.dropna(subset=["time_s", "current_mA"]).sort_values("time_s").reset_index(drop=True)
    if ca.empty:
        raise ValueError("No valid CA time/current data found in {}.".format(ca_csv))

    charge_mode = p["ca_charge_mode"]
    threshold_mA = float(p["ca_threshold_mA"])

    current_A_for_charge = current_for_charge(ca["current_mA"].to_numpy(), mode=charge_mode)
    cumulative_charge_C = cumulative_trapezoid_np(current_A_for_charge, ca["time_s"].to_numpy())
    cumulative_o2_mol = cumulative_charge_C / (4.0 * FARADAY_C_PER_MOL)

    ca["current_used_for_charge_A"] = current_A_for_charge
    ca["cumulative_charge_C"] = cumulative_charge_C
    ca["cumulative_O2_mol"] = cumulative_o2_mol
    ca["cumulative_O2_umol"] = cumulative_o2_mol * 1e6

    first_cross_s = first_downward_threshold_crossing(
        ca["time_s"].to_numpy(), ca["current_mA"].to_numpy(), threshold_mA=threshold_mA)

    extrema = find_ca_extrema(
        ca["time_s"].to_numpy(), ca["current_mA"].to_numpy(),
        smoothing_window_points=p["ca_extrema_smoothing_window_points"],
        min_separation_s=p["ca_extrema_min_separation_s"],
        min_prominence_mA=p["ca_extrema_min_prominence_mA"],
    )
    if not extrema.empty:
        extrema.insert(0, "sample_name", sample_name)
        extrema.insert(1, "source_file", Path(ca_csv).name)

    out_prefix = Path(out_prefix)
    processed_path = Path(str(out_prefix) + "_CA_processed.csv")
    extrema_path = Path(str(out_prefix) + "_CA_extrema.csv")
    current_png = Path(str(out_prefix) + "_CA_current.png")
    o2_png = Path(str(out_prefix) + "_CA_O2.png")
    ca.to_csv(processed_path, index=False)
    extrema.to_csv(extrema_path, index=False)

    dpi = int(p["dpi"])

    # fig = Figure(figsize=(8, 5))
    # ax = fig.add_subplot(111)
    # ax.plot(ca["time_min"], ca["current_mA"], label="CA current")
    # if not extrema.empty:
        # maxima = extrema[extrema["extremum_type"] == "maximum"]
        # minima = extrema[extrema["extremum_type"] == "minimum"]
        # if not maxima.empty:
            # ax.scatter(maxima["time_min"], maxima["current_mA"], marker="^", label="maxima")
        # if not minima.empty:
            # ax.scatter(minima["time_min"], minima["current_mA"], marker="v", label="minima")
    # ax.axhline(threshold_mA, linestyle="--", linewidth=1, label="{:g} mA threshold".format(threshold_mA))
    # if np.isfinite(first_cross_s):
        # ax.axvline(first_cross_s / 60.0, linestyle="--", linewidth=1, label="first crossing below threshold")
    # ax.set_xlabel("Time (min)")
    # ax.set_ylabel("Current (mA)")
    # ax.set_title("{} CA current vs time".format(sample_name))
    # ax.legend()
    # fig.tight_layout()
    # _save_fig(fig, current_png, dpi)

    # fig = Figure(figsize=(8, 5))
    # ax = fig.add_subplot(111)
    # ax.plot(ca["time_min"], ca["cumulative_O2_umol"], label="cumulative O2")
    # ax.set_xlabel("Time (min)")
    # ax.set_ylabel("Cumulative O2 generated (µmol)")
    # ax.set_title("{} CA charge-equivalent O2".format(sample_name))
    # ax.legend()
    # fig.tight_layout()
    # _save_fig(fig, o2_png, dpi)

    summary = {
        "CA_file": str(ca_csv),
        "CA_points": int(len(ca)),
        "CA_time_source": time_source,
        "CA_duration_s": float(ca["time_s"].iloc[-1] - ca["time_s"].iloc[0]),
        "CA_current_start_mA": float(ca["current_mA"].iloc[0]),
        "CA_current_end_mA": float(ca["current_mA"].iloc[-1]),
        "CA_current_mean_mA": float(ca["current_mA"].mean()),
        "CA_current_min_mA": float(ca["current_mA"].min()),
        "CA_current_max_mA": float(ca["current_mA"].max()),
        "CA_total_charge_C": float(ca["cumulative_charge_C"].iloc[-1]),
        "CA_total_O2_umol": float(ca["cumulative_O2_umol"].iloc[-1]),
        "CA_charge_mode": charge_mode,
        "CA_threshold_mA": threshold_mA,
        "CA_first_cross_below_threshold_s": float(first_cross_s) if np.isfinite(first_cross_s) else np.nan,
        "CA_n_minima": int((extrema["extremum_type"] == "minimum").sum()) if not extrema.empty else 0,
        "CA_n_maxima": int((extrema["extremum_type"] == "maximum").sum()) if not extrema.empty else 0,
        "CA_processed_csv": str(processed_path),
        "CA_extrema_csv": str(extrema_path),
        "CA_current_png": str(current_png),
        "CA_O2_png": str(o2_png),
    }
    print("{} CA: Q = {:.6g} C, O2 = {:.6g} umol, min/max events = {}/{}".format(
        sample_name, summary["CA_total_charge_C"], summary["CA_total_O2_umol"],
        summary["CA_n_minima"], summary["CA_n_maxima"]))
    return ca, extrema, summary


# ======================================================
# Cell-folder + plate entry points
# ======================================================

def _find_test_csv(cell_dir, test):
    """Find {anything}_{TEST}.csv in a cell folder (meta files never match)."""
    hits = sorted(Path(cell_dir).glob("*_{}.csv".format(test)))
    # Exclude our own outputs, which all contain '_processed'/'_extrema'.
    hits = [h for h in hits if "_processed" not in h.name and "_extrema" not in h.name]
    return hits[0] if hits else None


def analyze_cell_folder(cell_dir, params=None):
    """
    Analyze one triplet cell folder in place.

    Reads {stem}_PEIS.csv / {stem}_CV.csv / {stem}_CA.csv (whichever exist),
    writes plots + processed CSVs + {stem}_analysis_summary.csv into the same
    folder. Every stage is guarded: a failure in one test's analysis is recorded
    in the summary and never raises out of this function.
    """
    p = _resolve_analysis_params(params)
    cell_dir = Path(cell_dir)
    stem = cell_dir.name  # {plate_id}_{cell_id}

    summary = {"cell_folder": str(cell_dir), "stem": stem}
    m = re.match(r"^(.*)_(\d[A-Da-d])$", stem)
    if m:
        summary["plate_id"] = m.group(1)
        summary["cell_id"] = m.group(2).upper()

    R_s = None

    peis_csv = _find_test_csv(cell_dir, "PEIS")
    if peis_csv is not None:
        try:
            peis_summary = analyze_peis_csv(
                peis_csv, stem, cell_dir / "{}_PEIS_nyquist.png".format(stem), p)
            summary.update(peis_summary)
            R_s = peis_summary["R_s_ohm"]
        except Exception as e:
            summary["PEIS_error"] = "{}: {}".format(type(e).__name__, e)
            print("[analysis] PEIS failed for {}: {}".format(stem, summary["PEIS_error"]))

    cv_csv = _find_test_csv(cell_dir, "CV")
    if cv_csv is not None:
        try:
            _, cv_summary = process_cv_csv(
                cv_csv, R_s, stem,
                out_csv=cell_dir / "{}_CV_processed.csv".format(stem),
                plot_path=cell_dir / "{}_CV_plot.png".format(stem),
                p=p)
            summary.update(cv_summary)
        except Exception as e:
            summary["CV_error"] = "{}: {}".format(type(e).__name__, e)
            print("[analysis] CV failed for {}: {}".format(stem, summary["CV_error"]))

    ca_csv = _find_test_csv(cell_dir, "CA")
    if ca_csv is not None:
        try:
            _, _, ca_summary = analyze_ca_csv(ca_csv, stem, cell_dir / stem, p)
            summary.update(ca_summary)
        except Exception as e:
            summary["CA_error"] = "{}: {}".format(type(e).__name__, e)
            print("[analysis] CA failed for {}: {}".format(stem, summary["CA_error"]))

    if peis_csv is None and cv_csv is None and ca_csv is None:
        summary["note"] = "no PEIS/CV/CA data CSVs found"
        print("[analysis] nothing to analyze in {}".format(cell_dir))
        return summary

    try:
        pd.DataFrame([summary]).to_csv(cell_dir / "{}_analysis_summary.csv".format(stem), index=False)
    except Exception as e:
        print("[analysis] could not write summary for {}: {}".format(stem, e))
    return summary


_CELL_SUFFIX = re.compile(r"^\d[A-Da-d]$")


def _combined_cv_overlay(cell_dirs, out_dir, name, p, y_mode=None):
    """Overlay processed CVs from the given cell folders into one figure."""
    y_mode = p["cv_plot_y"] if y_mode is None else y_mode
    if str(y_mode).strip().lower() in {"mass", "massnorm", "mass_normalized"}:
        y_col, y_label, suffix = "MassNorm_mA_g", "Mass normalized current (mA/g)", "MassNorm"
    else:
        y_col, y_label, suffix = "GeoNorm_mA_cm2", "Geometric normalized current (mA/cm²)", "GeoNorm"

    frames = []
    for d in cell_dirs:
        f = Path(d) / "{}_CV_processed.csv".format(Path(d).name)
        if f.exists():
            try:
                frames.append(pd.read_csv(f))
            except Exception as e:
                print("[analysis] could not read {}: {}".format(f, e))
    if not frames:
        return None

    all_cv = pd.concat(frames, ignore_index=True)
    # fig = Figure(figsize=(8, 6))
    # ax = fig.add_subplot(111)
    # for sample_name, group in all_cv.groupby("sample_name", sort=False):
        # ax.plot(group["Processed_E_V"], group[y_col], label=str(sample_name), linewidth=2)
    # x_label = "Processed potential (V)"
    # if "processed_axis_label" in all_cv.columns and len(all_cv):
        # labels = all_cv["processed_axis_label"].dropna().unique()
        # if len(labels) == 1:
            # x_label = str(labels[0])
    # correction_text = "ref ON" if p["apply_reference_correction"] else "ref OFF"
    # correction_text += ", iR ON" if p["apply_ir_correction"] else ", iR OFF"
    # ax.set_xlabel(x_label)
    # ax.set_ylabel(y_label)
    # ax.set_title("Processed CV overlay, requested cycle {} ({} mode; {})".format(
        # p["cv_cycle_number"], p["cv_cycle_selection_mode"], correction_text))
    # if p["cv_x_min"] is not None or p["cv_x_max"] is not None:
        # ax.set_xlim(left=p["cv_x_min"], right=p["cv_x_max"])
    # if p["cv_y_min"] is not None or p["cv_y_max"] is not None:
        # ax.set_ylim(bottom=p["cv_y_min"], top=p["cv_y_max"])
    # ax.legend()
    # fig.tight_layout()
    # overlay_path = Path(out_dir) / "{}_CV_overlay_{}.png".format(name, suffix)
    # _save_fig(fig, overlay_path, int(p["dpi"]))
    all_cv.to_csv(Path(out_dir) / "{}_CV_processed_all_cells.csv".format(name), index=False)
    print("[analysis] saved combined processed CSV (graphing disabled)")
    return None


def analyze_plate(data_root, plate_id, params=None, y_mode=None):
    """
    Analyze every cell folder for one plate, then build the plate-level combined
    CV overlay and combined summary in {data_root}/{plate_id}_analysis/.
    """
    p = _resolve_analysis_params(params)
    data_root = Path(data_root)
    prefix = "{}_".format(plate_id)

    cell_dirs = []
    for d in sorted(data_root.iterdir()):
        if d.is_dir() and d.name.startswith(prefix) and _CELL_SUFFIX.match(d.name[len(prefix):]):
            cell_dirs.append(d)

    if not cell_dirs:
        print("[analysis] no cell folders found for plate {} in {}".format(plate_id, data_root))
        return []

    summaries = [analyze_cell_folder(d, params=p) for d in cell_dirs]

    out_dir = data_root / "{}_analysis".format(plate_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summaries).to_csv(out_dir / "{}_analysis_summary.csv".format(plate_id), index=False)

    _combined_cv_overlay(cell_dirs, out_dir, plate_id, p, y_mode)

    return summaries



def analyze_folder(folder, params=None, y_mode=None):
    """Analyze every cell folder directly inside `folder` (any plate id) and
    overlay all processed CVs into one combined graph, regardless of plate."""
    p = _resolve_analysis_params(params)
    folder = Path(folder)
    cell_dirs = [d for d in sorted(folder.iterdir())
                 if d.is_dir() and re.search(r"_\d[A-Da-d]$", d.name)]
    if not cell_dirs:
        print("[analysis] no cell folders (*_<row><col>) found in {}".format(folder))
        return []
    print("[analysis] found {} cell folder(s) in {}".format(len(cell_dirs), folder))
    summaries = [analyze_cell_folder(d, params=p) for d in cell_dirs]

    out_dir = folder / "combined_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = folder.name or "combined"
    pd.DataFrame(summaries).to_csv(out_dir / "{}_analysis_summary.csv".format(name), index=False)
    _combined_cv_overlay(cell_dirs, out_dir, name, p, y_mode)
    return summaries


# ======================================================
# CLI: retroactive analysis of existing folders

# ======================================================

def analyze_all(data_root, params=None):
    """Analyze every plate found in a triplet data root (cell dirs named {plate}_{cell})."""
    data_root = Path(data_root)
    plate_ids = set()
    for d in data_root.iterdir():
        if d.is_dir():
            m = re.match(r"^(.*)_(\d[A-Da-d])$", d.name)
            if m:
                plate_ids.add(m.group(1))
    if not plate_ids:
        print("[analysis] no {{plate}}_{{cell}} folders found in {}".format(data_root))
        return {}
    print("[analysis] found {} plate(s): {}".format(len(plate_ids), sorted(plate_ids)))
    return {pid: analyze_plate(data_root, pid, params=params) for pid in sorted(plate_ids)}


if __name__ == "__main__":
    args = sys.argv[1:]
    try:
        if len(args) == 1:
            p = Path(args[0])
            if any(_find_test_csv(p, t) for t in ("PEIS", "CV", "CA")):
                analyze_cell_folder(p)      # arg is a single cell folder
            else:
                analyze_folder(p)           # arg is a folder of runs: one combined overlay
        elif len(args) == 2:
            analyze_plate(args[0], args[1])
        else:
            print("usage:\n  python triplet_analysis.py <cell_folder>\n"
                  "  python triplet_analysis.py <folder>               (all runs, one overlay)\n"
                  "  python triplet_analysis.py <data_root> <plate_id> (one plate)")
    except Exception:
        traceback.print_exc()