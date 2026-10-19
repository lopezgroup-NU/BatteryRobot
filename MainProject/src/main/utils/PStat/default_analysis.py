"""Analyze electrochemical tests and save their results.

Function overview:
    compute_default_analysis: Choose an analyzer and format metrics and errors.
    analyze_peis: Estimate the Nyquist intercept and high-frequency resistance.
    peis_r_xintercept / peis_rs_positive_slope: Return those estimates in ohms.
    analyze_cv: Find onset, oxidation peaks, peak current, and threshold width.
    analyze_cp: Measure voltage drift, current change, failure time, and extrema.
    analyze_ca: Measure current drift, change, failure time, and extrema,
        accounting for cycles when detecting failure.
    analysis_subdoc: Select metrics and format them for Mongo.
    upsert_meta: Update metadata CSV fields using an atomic file replacement.
    analyze_into_meta: Compute metrics and save them to a run's metadata CSV.
    backfill: Refresh metadata for supported runs in a folder and its subfolders.

Private helpers read and clean data, smooth signals, fit slopes, find crossings
and extrema, format values, identify test types, and load stored parameters.
"""

from __future__ import annotations

import csv
import json
import math
import os
import re
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ANALYSIS_VERSION = "1"

_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")

# ---- tunables -------------------------------------------------------------
CV_J_THRESHOLD_MA_CM2 = 10.0       # current-density threshold for CV width (mA/cm^2)
CV_ONSET_WIN          = 10         # window size; override with params["cv_onset_win"]
CV_ONSET_SLOPE_K      = 5.0        # noise multiplier; override with params["cv_onset_slope_k"]
CP_FAILURE_I_A        = 0.01e-3    # failure threshold for |Im| (0.01 mA)
CP_EDGE_N             = 5          # endpoint sample count; override with params["cp_edge_n"]
EXTREMA_PROM_FRAC     = 0.02       # peak prominence as a fraction of signal range
EXTREMA_MAX_KEPT      = 50         # maximum peaks or troughs per signal

# Reuse triplet_analysis when available. Keep dataanalysis imports out of
# the per-test write path to avoid GUI and fitting dependencies.
# Other modules can import the shared PEIS estimators from here.
try:
    from utils.PStat.triplet_analysis import estimate_rs_from_positive_slope as _rs_ext
except ImportError:
    try:
        from triplet_analysis import estimate_rs_from_positive_slope as _rs_ext
    except ImportError:
        _rs_ext = None


# ---- small helpers --------------------------------------------------------

def _col(df, *names):
    """Return a numeric column, ignoring case and a leading # in its name."""
    lut = {}
    for c in df.columns:
        lut[str(c).lower().strip().lstrip("#").strip()] = c
    for n in names:
        c = lut.get(n.lower())
        if c is not None:
            return pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=float)
    raise KeyError("none of %s in %s" % (names, list(df.columns)))


def _smooth(y, win):
    win = max(1, int(win))
    return pd.Series(np.asarray(y, dtype=float)).rolling(win, center=True, min_periods=1).mean().to_numpy()


def _try(errs, name, fn, default=float("nan")):
    try:
        return fn()
    except Exception as e:
        errs.append("%s: %r" % (name, e))
        return default


def _fmt(v):
    if v is None:
        return ""
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        v = float(v)
        return "" if not math.isfinite(v) else v
    if isinstance(v, (list, dict)):
        return json.dumps(v)
    return v


# ---- PEIS -----------------------------------------------------------------

def _r_xintercept(zr, zi):
    """Return (resistance in ohms, method) for the Nyquist x-intercept.

    Use raw Zimag and arrays ordered from high to low frequency.
    """
    s = np.sign(zi)
    cross = np.where(s[:-1] * s[1:] < 0)[0]
    if len(cross):
        k = int(cross[0])  # Use the highest-frequency crossing.
        x0, x1, y0, y1 = zr[k], zr[k + 1], zi[k], zi[k + 1]
        return float(x0 + (0.0 - y0) * (x1 - x0) / (y1 - y0)), "interp"
    k = int(np.nanargmin(np.abs(zi)))
    return float(zr[k]), "min_abs_zimag"


def _rs_positive_slope_local(zr, zi):
    """Estimate Rs from the rising -Zimag branch.

    Arrays must run from high to low frequency.
    """
    y = -np.asarray(zi, dtype=float)
    x = np.asarray(zr, dtype=float)
    n = len(y)
    if n < 3:
        raise ValueError("too few points")
    k = 1
    while k < n and y[k] >= y[k - 1]:  # Follow the rising branch.
        k += 1
    k = min(max(k, 3), max(3, n // 2))
    m, b = np.polyfit(x[:k], y[:k], 1)
    if m <= 0:
        raise ValueError("no positive slope at high freq")
    return float(-b / m)


def _peis_arrays(df):
    """Return finite (frequency, Zreal, Zimag) arrays, highest frequency first."""
    freq = _col(df, "freq", "zfreq", "frequency")
    zr = _col(df, "zreal", "z_real", "zre")
    try:
        zi = _col(df, "zimag", "z_imag", "zim")
    except KeyError:
        zi = -_col(df, "reflected_zimag")
    ok = np.isfinite(freq) & np.isfinite(zr) & np.isfinite(zi)
    o = np.argsort(freq[ok])[::-1]
    return freq[ok][o], zr[ok][o], zi[ok][o]


def peis_r_xintercept(df):
    """Return the Nyquist x-intercept resistance in ohms."""
    _, zr, zi = _peis_arrays(df)
    return _r_xintercept(zr, zi)[0]


def peis_rs_positive_slope(df):
    """Estimate Rs in ohms, using triplet_analysis when available."""
    if _rs_ext is not None:
        try:
            return float(_rs_ext(df))
        except Exception:
            pass  # Use the local estimate if this fails.
    _, zr, zi = _peis_arrays(df)
    return _rs_positive_slope_local(zr, zi)


def analyze_peis(df, params, errs):
    _, zrr, zii = _peis_arrays(df)
    rx = _try(errs, "r_xintercept", lambda: _r_xintercept(zrr, zii), (float("nan"), ""))
    rs = _try(errs, "rs_positive_slope", lambda: peis_rs_positive_slope(df))

    return {
        "peis_r_xintercept_ohm": rx[0],
        "peis_r_xintercept_method": rx[1],
        "peis_rs_positive_slope_ohm": rs,
    }


# ---- CV -------------------------------------------------------------------

def _pick_cycle(cyc):
    """Select the second cycle label, the only label, or all data if none exist."""
    vals = np.unique(cyc[np.isfinite(cyc)])
    if len(vals) >= 2:
        c = vals[1]
    elif len(vals) == 1:
        c = vals[0]
    else:
        return None, "all"
    return cyc == c, c


def _strict_increasing(v, i):
    o = np.argsort(v)
    v, i = v[o], i[o]
    keep = np.concatenate(([True], np.diff(v) > 1e-12))
    return v[keep], i[keep]


def _window_slopes(vv, ii, w):
    """Fit a slope for each sliding window of w points."""
    cx = np.cumsum(np.insert(vv, 0, 0.0))
    cy = np.cumsum(np.insert(ii, 0, 0.0))
    cxx = np.cumsum(np.insert(vv * vv, 0, 0.0))
    cxy = np.cumsum(np.insert(vv * ii, 0, 0.0))
    sx = cx[w:] - cx[:-w]
    sy = cy[w:] - cy[:-w]
    sxx = cxx[w:] - cxx[:-w]
    sxy = cxy[w:] - cxy[:-w]
    den = w * sxx - sx * sx
    den = np.where(den > 0, den, np.nan)
    return (w * sxy - sx * sy) / den


def _onset(v2, i2, fwd, win=CV_ONSET_WIN, k=CV_ONSET_SLOPE_K):
    """Return (onset voltage, method) for the anodic branch.

    Look for two rising-slope windows above the baseline threshold.
    Falls back to a tangent fit, then a 5% current-rise threshold.
    """
    vv, ii_raw = _strict_increasing(v2[fwd], i2[fwd])
    if len(vv) < max(10, 2 * win):
        raise ValueError("anodic branch too short")
    try:
        sl = _window_slopes(vv, ii_raw, win)
        foot = vv[: len(sl)] <= vv[0] + 0.30 * (vv[-1] - vv[0])
        ref = sl[foot] if int(foot.sum()) >= 3 else sl
        ref = ref[np.isfinite(ref)]
        m_b = float(np.median(ref))
        mad = float(np.median(np.abs(ref - m_b))) * 1.4826
        rng_sl = float(np.nanmax(sl)) - m_b
        thr = m_b + max(k * mad, 0.05 * rng_sl)  # Keep a threshold even without noise.
        ok = np.isfinite(sl) & (sl > 0) & (sl >= thr)
        hit = np.where(ok[:-1] & ok[1:])[0]
        if len(hit):
            return float(vv[int(hit[0])]), "slope_window"
    except Exception:
        pass
    ii = _smooth(ii_raw, max(5, len(ii_raw) // 50))
    lo = vv <= vv[0] + 0.30 * (vv[-1] - vv[0])
    base = float(np.median(ii[lo])) if lo.any() else float(ii[0])
    try:
        didv = np.gradient(ii, vv)
        j = int(np.argmax(didv))
        m = didv[j]
        if m <= 0:
            raise ValueError("no rising slope")
        von = vv[j] + (base - ii[j]) / m
        return float(np.clip(von, vv[0], vv[-1])), "tangent"
    except Exception:
        th = base + 0.05 * (float(np.max(ii)) - base)
        idx = np.where(ii >= th)[0]
        if not len(idx):
            raise ValueError("current never rises above baseline")
        return float(vv[idx[0]]), "threshold_5pct"


def _ox_peaks(v2, i2, fwd):
    """Return anodic current peaks as a list of {"V", "I"} dictionaries."""
    vv, ii = _strict_increasing(v2[fwd], i2[fwd])
    n = len(ii)
    if n < 7:
        return []
    iis = _smooth(ii, max(3, n // 100))
    rng = float(np.max(iis) - np.min(iis))
    resid_mad = 1.4826 * float(np.median(np.abs(ii - iis)))
    if rng <= 0 or rng <= 6.0 * resid_mad:  # Ignore signals dominated by noise.
        return []
    prom = EXTREMA_PROM_FRAC * rng
    w = max(3, n // 50)
    wp = max(w, n // 10)
    s = pd.Series(iis)
    rmax = s.rolling(2 * w + 1, center=True, min_periods=1).max().to_numpy()
    lmin = s.rolling(wp + 1, min_periods=1).min().to_numpy()
    rmin = s[::-1].rolling(wp + 1, min_periods=1).min().to_numpy()[::-1]
    # Require a drop on both sides to exclude saturation plateaus.
    cand = _collapse_runs(np.where((iis >= rmax - 1e-15) & (iis - lmin >= prom) & (iis - rmin >= prom))[0])
    cand = cand[(cand > 0) & (cand < n - 1)]
    kept = []
    for k in cand[np.argsort(iis[cand])[::-1]]:
        if all(abs(int(k) - j) > w for j in kept):
            kept.append(int(k))
    kept = sorted(kept)[:20]
    return [{"V": round(float(vv[k]), 5), "I": float("%.6g" % ii[k])} for k in kept]


def _cross_v(vb, ib, th, direction, pick="first"):
    """Find the voltage where current crosses "th" in scan order.

    direction is "up" or "down"; pick selects the "first" or "last" crossing.
    """
    d = np.asarray(ib, dtype=float) - th
    s = np.sign(d)
    hits = []
    for k in np.where(s[:-1] * s[1:] < 0)[0]:
        if direction == "up" and d[k] < 0.0 < d[k + 1]:
            hits.append(int(k))
        elif direction == "down" and d[k] > 0.0 > d[k + 1]:
            hits.append(int(k))
    if not hits:
        raise ValueError("no %s-crossing of %.4g A" % (direction, th))
    k = hits[0] if pick == "first" else hits[-1]
    frac = (th - ib[k]) / (ib[k + 1] - ib[k])
    return float(vb[k] + frac * (vb[k + 1] - vb[k]))


def analyze_cv(df, params, errs):
    v = _col(df, "vf")
    i = _col(df, "im")
    try:
        cyc = _col(df, "cycle")
    except KeyError:
        cyc = None

    area = params.get("area_cm2", params.get("area", 1.0))
    area = float(area) if area else 1.0
    i_th = CV_J_THRESHOLD_MA_CM2 * 1e-3 * area  # A

    if cyc is not None:
        m, cycle_used = _pick_cycle(cyc)
        if m is None:
            m = np.ones(len(v), dtype=bool)
    else:
        m, cycle_used = np.ones(len(v), dtype=bool), "all"
    v2, i2 = v[m], i[m]

    dv = np.gradient(_smooth(v2, 5))
    fwd, rev = dv > 0, dv < 0

    try:
        onset_win = int(float(params.get("cv_onset_win", CV_ONSET_WIN)))
    except Exception:
        onset_win = CV_ONSET_WIN
    try:
        onset_k = float(params.get("cv_onset_slope_k", CV_ONSET_SLOPE_K))
    except Exception:
        onset_k = CV_ONSET_SLOPE_K
    onset = _try(errs, "onset", lambda: _onset(v2, i2, fwd, onset_win, onset_k), (float("nan"), ""))
    peaks = _try(errs, "ox_peaks", lambda: _ox_peaks(v2, i2, fwd), [])
    imax_k = int(np.nanargmax(i))
    # Bound the high-current region: last upward crossing, first downward crossing.
    width = _try(errs, "capacitance_width", lambda: float(
        _cross_v(v2[fwd], i2[fwd], i_th, "up", pick="last") - _cross_v(v2[rev], i2[rev], i_th, "down", pick="first")))

    return {
        "cv_cycle_used": cycle_used,
        "cv_onset_v": onset[0],
        "cv_onset_method": onset[1],
        "cv_onset_win": onset_win,
        "cv_onset_slope_k": onset_k,
        "cv_ox_peaks_json": peaks,
        "cv_n_ox_peaks": len(peaks),
        "cv_i_max_a": float(i[imax_k]),
        "cv_v_at_i_max_v": float(v[imax_k]),
        "cv_width_v": width,
        "cv_capacitance_j_threshold_ma_cm2": CV_J_THRESHOLD_MA_CM2,
        "cv_area_cm2": area,
    }


# ---- CP -------------------------------------------------------------------

def _collapse_runs(idxs):
    """Keep the middle index of each consecutive group of candidates."""
    if not len(idxs):
        return np.asarray(idxs, dtype=int)
    out, start, prev = [], int(idxs[0]), int(idxs[0])
    for k in idxs[1:]:
        k = int(k)
        if k == prev + 1:
            prev = k
        else:
            out.append((start + prev) // 2)
            start = prev = k
    out.append((start + prev) // 2)
    return np.asarray(out, dtype=int)


def _local_extrema(y):
    """Return peak and trough indices, filtered by prominence and spacing."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 7:
        return [], []
    ys = _smooth(y, max(3, n // 200))
    rng = float(np.nanmax(ys) - np.nanmin(ys))
    resid_mad = 1.4826 * float(np.nanmedian(np.abs(y - ys)))
    if not np.isfinite(rng) or rng <= 0 or rng <= 6.0 * resid_mad:
        return [], []
    prom = EXTREMA_PROM_FRAC * rng
    w = max(5, n // 100)            # local window and minimum spacing
    wp = max(w, n // 10)            # wider window for prominence
    s = pd.Series(ys)
    rmax = s.rolling(2 * w + 1, center=True, min_periods=1).max().to_numpy()
    rmin = s.rolling(2 * w + 1, center=True, min_periods=1).min().to_numpy()
    pmax = s.rolling(2 * wp + 1, center=True, min_periods=1).max().to_numpy()
    pmin = s.rolling(2 * wp + 1, center=True, min_periods=1).min().to_numpy()

    def pick(mask, high):
        idxs = _collapse_runs(np.where(mask)[0])
        idxs = idxs[(idxs > 0) & (idxs < n - 1)]
        order = idxs[np.argsort(ys[idxs])[::-1]] if high else idxs[np.argsort(ys[idxs])]
        kept = []
        for k in order:
            if all(abs(int(k) - j) > w for j in kept):
                kept.append(int(k))
        return sorted(kept)[:EXTREMA_MAX_KEPT]

    mx = pick((ys >= rmax - 1e-15) & (ys - pmin >= prom), True)
    mn = pick((ys <= rmin + 1e-15) & (pmax - ys >= prom), False)
    return mx, mn


def _extrema_json(t, y, idxs):
    return [{"t": round(float(t[k]), 3), "value": float("%.6g" % y[k])} for k in idxs]


def analyze_cp(df, params, errs):
    t = _col(df, "time", "t", "t_hold")
    v = _col(df, "vf")
    i = _col(df, "im")
    n = len(t)
    try:
        edge_n = int(float(params.get("cp_edge_n", CP_EDGE_N)))
    except Exception:
        edge_n = CP_EDGE_N
    k = max(1, min(edge_n, n))

    # Use endpoint medians to reduce noise.
    i_start, i_end = float(np.median(i[:k])), float(np.median(i[-k:]))
    v_start, v_end = float(np.median(v[:k])), float(np.median(v[-k:]))
    dur = float(t[-1] - t[0])
    slope = (v_end - v_start) / dur if dur > 0 else float("nan")
    slope_fit = _try(errs, "slope_fit", lambda: float(np.polyfit(t, v, 1)[0]))

    # Failure starts at the first drop below threshold after reaching it.
    absi = np.abs(i)
    armed = absi >= CP_FAILURE_I_A
    ttf = float("nan")
    if armed.any():
        first_on = int(np.argmax(armed))
        below = np.where(~armed[first_on:])[0]
        if len(below):
            status = "failed"
            ttf = float(t[first_on + int(below[0])] - t[0])
        else:
            status = "live"
    else:
        status = "never_above_threshold"

    vmx, vmn = _try(errs, "vf_extrema", lambda: _local_extrema(v), ([], []))
    imx, imn = _try(errs, "im_extrema", lambda: _local_extrema(i), ([], []))

    out = {
        "cp_slope_v_per_s": slope,
        "cp_slope_fit_v_per_s": slope_fit,
        "cp_i_start_a": i_start,
        "cp_i_end_a": i_end,
        "cp_edge_n": k,
        # "cp_delta_i_start_minus_end_a": i_start - i_end,
        "cp_delta_i_end_minus_start_a": i_end - i_start,
        "cp_time_to_failure_s": ttf,
        "cp_status": status,
        "cp_failure_threshold_a": CP_FAILURE_I_A,
        "cp_vf_min": float(np.nanmin(v)),
        "cp_vf_max": float(np.nanmax(v)),
        "cp_im_min": float(np.nanmin(i)),
        "cp_im_max": float(np.nanmax(i)),
        "cp_vf_local_max_json": _extrema_json(t, v, vmx),
        "cp_vf_local_min_json": _extrema_json(t, v, vmn),
        "cp_im_local_max_json": _extrema_json(t, i, imx),
        "cp_im_local_min_json": _extrema_json(t, i, imn),
        "cp_n_vf_local_max": len(vmx),
        "cp_n_vf_local_min": len(vmn),
    }
    return out


def analyze_ca(df, params, errs):
    """Summarize CA current drift, change, failure time, and extrema.

    Prefer t_hold. For cyclic data, failure requires all remaining cycles'
    peak absolute currents to stay below threshold.
    """
    i = _col(df, "im")
    try:
        tb = _col(df, "t_hold")
    except KeyError:
        tb = _col(df, "time", "t")
    try:
        cyc = _col(df, "cycle")
    except KeyError:
        cyc = None

    n = len(tb)
    try:
        edge_n = int(float(params.get("ca_edge_n", params.get("cp_edge_n", CP_EDGE_N))))
    except Exception:
        edge_n = CP_EDGE_N
    k = max(1, min(edge_n, n))
    i_start, i_end = float(np.median(i[:k])), float(np.median(i[-k:]))
    dur = float(tb[-1] - tb[0])
    slope = (i_end - i_start) / dur if dur > 0 else float("nan")

    vals = np.unique(cyc[np.isfinite(cyc)]) if cyc is not None else np.asarray([])
    ttf, status = float("nan"), "never_above_threshold"
    if len(vals) >= 2:
        t0s, maxabs = [], []
        for c in vals:
            m = cyc == c
            t0s.append(float(np.min(tb[m])))
            maxabs.append(float(np.max(np.abs(i[m]))))
        order = np.argsort(t0s)
        t0s = [t0s[j] for j in order]
        dead = np.asarray([maxabs[j] for j in order]) < CP_FAILURE_I_A
        kfail = None
        for j in range(len(dead)):
            if dead[j:].all():
                kfail = j
                break
        if kfail is None:
            status = "live"
        elif kfail == 0:
            status = "never_above_threshold"
        else:
            status = "failed"
            ttf = float(t0s[kfail] - t0s[0])
    else:
        armed = np.abs(i) >= CP_FAILURE_I_A
        if armed.any():
            first_on = int(np.argmax(armed))
            below = np.where(~armed[first_on:])[0]
            if len(below):
                status = "failed"
                ttf = float(tb[first_on + int(below[0])] - tb[0])
            else:
                status = "live"

    imx, imn = _try(errs, "im_extrema", lambda: _local_extrema(i), ([], []))

    return {
        "ca_slope_a_per_s": slope,
        "ca_i_start_a": i_start,
        "ca_i_end_a": i_end,
        "ca_edge_n": k,
        "ca_delta_i_start_minus_end_a": i_start - i_end,
        "ca_time_to_failure_s": ttf,
        "ca_status": status,
        "ca_failure_threshold_a": CP_FAILURE_I_A,
        "ca_im_min": float(np.nanmin(i)),
        "ca_im_max": float(np.nanmax(i)),
        "ca_im_local_max_json": _extrema_json(tb, i, imx),
        "ca_im_local_min_json": _extrema_json(tb, i, imn),
        "ca_n_im_local_max": len(imx),
        "ca_n_im_local_min": len(imn),
    }


# ---- dispatch -------------------------------------------------------------

_DISPATCH = {
    "PEIS": analyze_peis,
    "EIS": analyze_peis,
    "CV": analyze_cv,
    "CP": analyze_cp,
    "CA": analyze_ca,
    "CACYCLE": analyze_ca,
}


# Metrics saved to Mongo; metadata CSVs keep the full analysis.
# List fields drop their _json suffix when stored in Mongo.
MONGO_ANALYSIS_FIELDS = {
    "peis": ("peis_r_xintercept_ohm",),
    "cv": ("cv_onset_v", "cv_ox_peaks", "cv_i_max_a", "cv_v_at_i_max_v",
           "cv_width_v"),
    "cp": ("cp_slope_v_per_s", "cp_i_start_a", "cp_i_end_a",
           "cp_delta_i_start_minus_end_a", "cp_time_to_failure_s", "cp_status",
           "cp_vf_min", "cp_vf_max", "cp_im_min", "cp_im_max",
           "cp_vf_local_max", "cp_vf_local_min", "cp_im_local_max", "cp_im_local_min"),
    "ca": ("ca_slope_a_per_s", "ca_i_start_a", "ca_i_end_a",
           "ca_delta_i_start_minus_end_a", "ca_time_to_failure_s", "ca_status",
           "ca_im_min", "ca_im_max", "ca_im_local_max", "ca_im_local_min"),
}
_MONGO_KEEP = frozenset(
    f for fields in MONGO_ANALYSIS_FIELDS.values() for f in fields
) | {"error", "note"}   # Keep analysis failures visible.


def analysis_subdoc(test, data, params=None):
    """Return selected metrics for Mongo, omitting blank values.

    Decode *_json fields into lists and drop the suffix.
    """
    out = {}
    for k, v in compute_default_analysis(test, data, params).items():
        if v is None or v == "":
            continue
        if k.endswith("_json") and isinstance(v, str):
            try:
                v = json.loads(v)
                k = k[:-5]
            except Exception:
                pass
        if k not in _MONGO_KEEP:
            continue
        out[k] = v
    return out


def upsert_meta(meta_path, updates):
    """Update or create a field/value CSV, preserving unrelated rows.

    Remove matching legacy analysis_ fields and replace the file atomically.
    """
    meta_path = str(meta_path)
    rows = []
    if os.path.exists(meta_path):
        with open(meta_path, "r", newline="") as f:
            raw = [r for r in csv.reader(f) if r]
        if raw and [c.strip().lower() for c in raw[0][:2]] == ["field", "value"]:
            raw = raw[1:]
        rows = [[r[0], r[1] if len(r) > 1 else ""] for r in raw]
    seen = {}
    for idx, r in enumerate(rows):
        seen.setdefault(r[0], idx)
    legacy = set("analysis_" + kk for kk in updates) & set(seen)
    if legacy:
        rows = [r for r in rows if r[0] not in legacy]
        seen = {}
        for idx, r in enumerate(rows):
            seen.setdefault(r[0], idx)
    for kk, vv in updates.items():
        vv = _fmt(vv)
        vv = "" if vv is None else vv
        if kk in seen:
            rows[seen[kk]] = [kk, vv]
        else:
            seen[kk] = len(rows)
            rows.append([kk, vv])
    d = os.path.dirname(meta_path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["field", "value"])
            w.writerows(rows)
        os.replace(tmp, meta_path)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return meta_path


def analyze_into_meta(test, data, params, meta_path):
    """Compute a run's metrics and update its metadata CSV."""
    return upsert_meta(meta_path, compute_default_analysis(test, data, params))


BACKFILL_TESTS = ("PEIS", "EIS", "CV", "CP", "CA", "CA_CYCLE")


def _test_token(stem):
    s = stem.lower()
    if s.endswith("_ca_cycle") or s.endswith("_ca cycle"):
        return "CA_CYCLE"
    return stem.rsplit("_", 1)[-1].upper()


def _params_from_meta(meta_path):
    """Read stored parameters from a field/value metadata CSV."""
    try:
        df = pd.read_csv(meta_path, dtype=str).fillna("")
        return dict(zip(df["field"], df["value"]))
    except Exception:
        return {}


def backfill(root):
    """Refresh metadata for supported runs under root.

    Continue after file errors and return the number of successful updates.
    """
    ok = bad = 0
    for p in sorted(Path(root).rglob("*.csv")):
        if p.name.endswith("_meta.csv"):
            continue
        test = _test_token(p.stem)
        if test not in BACKFILL_TESTS:
            continue
        meta = p.with_name(p.stem + "_meta.csv")
        try:
            analyze_into_meta(test, pd.read_csv(p), _params_from_meta(meta), meta)
            ok += 1
        except Exception as e:
            bad += 1
            print("FAILED %s: %r" % (p.name, e))
    print("upserted %d meta files, %d failures" % (ok, bad))
    return ok


def compute_default_analysis(test, data, params=None):
    """Return formatted metrics, recording analysis errors in the result."""
    out = {}
    try:
        if data is None or len(data) == 0:
            return {"note": "no data"}
        df = data if isinstance(data, pd.DataFrame) else pd.DataFrame(data)
        fn = _DISPATCH.get(re.sub(r"[\s_]+", "", str(test).strip().upper()))
        if fn is None:
            return {"note": "no analyzer for test %r (have: %s)"
                    % (test, ",".join(sorted(_DISPATCH)))}
        errs = []
        out = fn(df, dict(params or {}), errs)
        if errs:
            out["errors"] = "; ".join(errs)
        out["version"] = ANALYSIS_VERSION
    except Exception as e:
        out["error"] = repr(e)
    return {kk: _fmt(vv) for kk, vv in out.items()}