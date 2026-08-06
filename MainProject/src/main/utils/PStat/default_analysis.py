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
CV_J_THRESHOLD_MA_CM2 = 10.0       # width metric threshold, mA/cm^2
CV_ONSET_WIN          = 10         # onset: points per sliding window (params["cv_onset_win"] overrides)
CV_ONSET_SLOPE_K      = 5.0        # onset: slope must exceed foot median + K*MAD (params["cv_onset_slope_k"])
CP_FAILURE_I_A        = 0.01e-3    # |Im| below this counts as failure (0.01 mA)
CP_EDGE_N             = 5          # "first/last x datapoints" for start/end values (params["cp_edge_n"] overrides)
EXTREMA_PROM_FRAC     = 0.02       # local-extrema prominence, fraction of signal range
EXTREMA_MAX_KEPT      = 50         # cap on reported local extrema per signal

# Prefer the existing implementation from triplet_analysis when present.
# NOTE: dataanalysis.py is deliberately NOT imported here. It executes
# `import matplotlib.pyplot` at import time (Tk-root hazard in GUI worker
# threads) and pulls BUMPS + the `impedance` package, which don't belong in
# the per-test write path. Its minR is a DREAM-fit seed, not a reported
# metric; the light PEIS estimators live here canonically. If dataanalysis
# ever needs them, it should import peis_r_xintercept / peis_rs_positive_slope
# FROM this module -- never the other way around.
try:
    from utils.PStat.triplet_analysis import estimate_rs_from_positive_slope as _rs_ext
except ImportError:
    try:
        from triplet_analysis import estimate_rs_from_positive_slope as _rs_ext
    except ImportError:
        _rs_ext = None


# ---- small helpers --------------------------------------------------------

def _col(df, *names):
    """Case-insensitive column fetch ('# Point' == 'point'). Returns float ndarray."""
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
    """Nyquist x-intercept. Arrays ordered high -> low freq; zi is raw Zimag.
    Returns (R_ohm, method)."""
    s = np.sign(zi)
    cross = np.where(s[:-1] * s[1:] < 0)[0]
    if len(cross):
        k = int(cross[0])  # highest-frequency crossing = ohmic intercept
        x0, x1, y0, y1 = zr[k], zr[k + 1], zi[k], zi[k + 1]
        return float(x0 + (0.0 - y0) * (x1 - x0) / (y1 - y0)), "interp"
    k = int(np.nanargmin(np.abs(zi)))
    return float(zr[k]), "min_abs_zimag"


def _rs_positive_slope_local(zr, zi):
    """Fit the high-frequency ascending branch of (-Zim) vs Zreal; x-intercept = Rs.
    Arrays ordered high -> low freq."""
    y = -np.asarray(zi, dtype=float)
    x = np.asarray(zr, dtype=float)
    n = len(y)
    if n < 3:
        raise ValueError("too few points")
    k = 1
    while k < n and y[k] >= y[k - 1]:  # walk down-freq while -Zim still rising
        k += 1
    k = min(max(k, 3), max(3, n // 2))
    m, b = np.polyfit(x[:k], y[:k], 1)
    if m <= 0:
        raise ValueError("no positive slope at high freq")
    return float(-b / m)


def _peis_arrays(df):
    """(freq, zreal, zimag) as finite float arrays ordered high -> low freq."""
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
    """Nyquist x-intercept resistance (ohm). Canonical implementation --
    import from here (vial or plate side) instead of re-implementing."""
    _, zr, zi = _peis_arrays(df)
    return _r_xintercept(zr, zi)[0]


def peis_rs_positive_slope(df):
    """Rs from the high-frequency positive-slope branch (ohm). Defers to
    triplet_analysis.estimate_rs_from_positive_slope when importable."""
    if _rs_ext is not None:
        try:
            return float(_rs_ext(df))
        except Exception:
            pass  # signature/impl mismatch -> local fallback
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
    """Return mask + label for the 2nd distinct Cycle value (works for 0- or 1-indexed)."""
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
    """Least-squares slope of every length-w sliding window (vectorized)."""
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
    """Onset on the anodic branch. Primary: slide a `win`-point window along the branch,
    LS-fit the slope in each; "significant" = slope above (median + k*MAD) of the window
    slopes in the baseline foot (lowest 30% of V range), floored at 5% of the slope
    dynamic range; two consecutive windows must pass. Onset = V of the FIRST point of
    the first passing window. Fallbacks: tangent-intersection, then 5%-of-max threshold.
    Returns (V_onset, method)."""
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
        thr = m_b + max(k * mad, 0.05 * rng_sl)  # noise-scaled, floored for noiseless data
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
    """Local maxima of I on the anodic branch. JSON-able list of {"V","I"}."""
    vv, ii = _strict_increasing(v2[fwd], i2[fwd])
    n = len(ii)
    if n < 7:
        return []
    iis = _smooth(ii, max(3, n // 100))
    rng = float(np.max(iis) - np.min(iis))
    resid_mad = 1.4826 * float(np.median(np.abs(ii - iis)))
    if rng <= 0 or rng <= 6.0 * resid_mad:  # no structure above the noise floor
        return []
    prom = EXTREMA_PROM_FRAC * rng
    w = max(3, n // 50)
    wp = max(w, n // 10)
    s = pd.Series(iis)
    rmax = s.rolling(2 * w + 1, center=True, min_periods=1).max().to_numpy()
    lmin = s.rolling(wp + 1, min_periods=1).min().to_numpy()
    rmin = s[::-1].rolling(wp + 1, min_periods=1).min().to_numpy()[::-1]
    # a real oxidative peak descends on both sides; a saturation plateau does not
    cand = _collapse_runs(np.where((iis >= rmax - 1e-15) & (iis - lmin >= prom) & (iis - rmin >= prom))[0])
    cand = cand[(cand > 0) & (cand < n - 1)]
    kept = []
    for k in cand[np.argsort(iis[cand])[::-1]]:
        if all(abs(int(k) - j) > w for j in kept):
            kept.append(int(k))
    kept = sorted(kept)[:20]
    return [{"V": round(float(vv[k]), 5), "I": float("%.6g" % ii[k])} for k in kept]


def _cross_v(vb, ib, th, direction, pick="first"):
    """V where I crosses `th` on a branch (arrays in scan order).
    direction: 'up'|'down'; pick: 'first'|'last' matching crossing in scan order."""
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
    # crossings bounding the high-current region: last up-cross going in, first down-cross coming out
    width = _try(errs, "capacitance_width", lambda: float(
        _cross_v(v2[fwd], i2[fwd], i_th, "up", pick="last")
        - _cross_v(v2[rev], i2[rev], i_th, "down", pick="first")))

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
        "cv_capacitance_width_v": width,
        "cv_capacitance_j_threshold_ma_cm2": CV_J_THRESHOLD_MA_CM2,
        "cv_area_cm2": area,
    }


# ---- CP -------------------------------------------------------------------

def _collapse_runs(idxs):
    """Contiguous candidate-index runs (flat plateaus) -> single middle representative."""
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
    """Indices of local maxima/minima of y (prominence + min-separation filtered)."""
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
    w = max(5, n // 100)            # min separation / "is local max" window
    wp = max(w, n // 10)            # prominence measured over a wider window
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

    # start/end = center (median) of the first/last k datapoints
    i_start, i_end = float(np.median(i[:k])), float(np.median(i[-k:]))
    v_start, v_end = float(np.median(v[:k])), float(np.median(v[-k:]))
    dur = float(t[-1] - t[0])
    slope = (v_end - v_start) / dur if dur > 0 else float("nan")
    slope_fit = _try(errs, "slope_fit", lambda: float(np.polyfit(t, v, 1)[0]))

    # failure: first drop below threshold after having been at/above it; "live" if it reaches end of run
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
    """CA / CA Cycle. Emits ONLY the spec fields: slope (begin -> end of run),
    start/end current (median of first/last edge_n pts), delta-I, time-to-failure
    at CP_FAILURE_I_A ("live" if end of run reached), and Im min/max + local
    extrema. Internals: timebase prefers gap-free t_hold; on cyclic data (>=2
    Cycle values) failure is judged per cycle (max|Im| per cycle) so polarity
    flips through zero don't fire false failures."""
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


# Fields kept in the Mongo "analysis" subdocument -- the spec metrics only.
# The *_meta.csv files always keep everything (methods, knobs, version, errors);
# edit these tuples to change what lands in Mongo. Note: *_json names appear
# here WITHOUT the suffix (they become real arrays in Mongo).
MONGO_ANALYSIS_FIELDS = {
    "peis": ("peis_r_xintercept_ohm",),
    "cv": ("cv_onset_v", "cv_ox_peaks", "cv_i_max_a", "cv_v_at_i_max_v",
           "cv_capacitance_width_v"),
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
) | {"error", "note"}   # whole-analysis failures stay visible in Mongo


def analysis_subdoc(test, data, params=None):
    """Mongo-ready analysis subdocument: spec metrics only (MONGO_ANALYSIS_FIELDS).
    *_json fields become real lists (suffix dropped) and blank values are omitted,
    so e.g. a live run simply has no ca_time_to_failure_s key. Methods, knobs,
    counts, and version stay in the *_meta.csv only."""
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
    """Upsert field/value rows into a *_meta.csv (creates it if missing).
    Existing fields are updated in place, new fields append at the bottom;
    all other rows and their order are preserved. Atomic write (tmp + os.replace)."""
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
    """Compute default analysis for one run and upsert it into its *_meta.csv.
    Use for backfilling existing runs or recomputing after a tunable change."""
    return upsert_meta(meta_path, compute_default_analysis(test, data, params))


BACKFILL_TESTS = ("PEIS", "EIS", "CV", "CP", "CA", "CA_CYCLE")


def _test_token(stem):
    s = stem.lower()
    if s.endswith("_ca_cycle") or s.endswith("_ca cycle"):
        return "CA_CYCLE"
    return stem.rsplit("_", 1)[-1].upper()


def _params_from_meta(meta_path):
    """field/value meta CSV -> dict (stored area_cm2 / cp_edge_n etc. get applied)."""
    try:
        df = pd.read_csv(meta_path, dtype=str).fillna("")
        return dict(zip(df["field"], df["value"]))
    except Exception:
        return {}


def backfill(root):
    """Recompute analysis for every run under `root` and upsert into each
    *_meta.csv. Idempotent; per-file failures print and don't stop the sweep.
    Usage: backfill(r"C:/.../ciara_new_data/data") -- forward slashes work on Windows."""
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
    """Rows to append to the meta CSV for `test`. Never raises."""
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