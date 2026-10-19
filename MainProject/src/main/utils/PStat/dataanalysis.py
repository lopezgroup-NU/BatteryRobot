# dataanalysis.py
# PStat analysis and plotting for EIS, CV, CA/CP, and capacitance tests.
# Combines dataanalysis.py, BUMPS.py, and helpers from cv.py, ca.py, and cp.py.
# Original functions by Thanh Nguyen & Willa Brenneis.
#
# After reinstalling bumps, add this at the end of fit() in fitters.py
# so it returns the parameter summary expected by BUMPS.fitproblem:
#
#   obj = {}
#   obj["final chisq"] = problem.chisq_str()
#   err = driver.stderr_from_cov()
#   for k, v, dv in zip(driver.problem.labels(), driver.problem.getp(), err):
#       obj[str(k)] = format_uncertainty(v, dv)
#   return result, obj

import inspect
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None

# bumps/dill are only needed for circuit fitting (BUMPS / DataAnalyzer)
try:
    import bumps.names as bmp
    from bumps.fitters import fit
    from bumps.formatnum import format_uncertainty
    import dill
    HAVE_BUMPS = True
except ImportError:
    HAVE_BUMPS = False

try:
    from ..MathUtils import kinetic_fit          # Butler-Volmer / Tafel fit for CA/CV
except Exception:
    kinetic_fit = None


def _as_df(source, index_col=None) -> pd.DataFrame:
    """Read a CSV or use the supplied DataFrame."""
    if isinstance(source, (str, Path)):
        return pd.read_csv(source, index_col=index_col)
    return source


# =====================================================================
# EIS / PEIS / GEIS interpretation
# =====================================================================

def eis_interpret(source):
    """Estimate the EIS intercept at the lowest nonnegative -Zimag value."""
    df = _as_df(source)
    if "reflected_zimag" not in df.columns:
        df = df.copy()
        df["reflected_zimag"] = [-v for v in df["zimag"]]

    df_no_negatives = df[df.reflected_zimag >= 0]
    min_index = df_no_negatives["reflected_zimag"].idxmin()
    return {
        "minima_zreal": df_no_negatives["zreal"].loc[min_index],
        "reflected_zimag": df_no_negatives["reflected_zimag"].loc[min_index],
        "index": min_index,
    }

peis_interpret = eis_interpret
geis_interpret = eis_interpret


# =====================================================================
# CV interpretation
# =====================================================================

def find_peaks_and_zero_crossings(data):
    zero_index = np.argmax(data["Vf"] >= 0)
    positive_peak_index = np.argmax(data["Im"][zero_index:]) + zero_index
    zero_cross_index = np.argmax(np.diff(np.sign(data["Vf"][positive_peak_index:])) != 0) + positive_peak_index
    negative_peak_index = np.argmin(data["Im"][zero_cross_index:]) + zero_cross_index
    return positive_peak_index, zero_cross_index, negative_peak_index


def cv_interpret(filename):
    """Return (vf_max - vf_min, vf_max, vf_min) at currents closest to ±24 µA."""
    df = _as_df(filename, index_col="# Point")

    positive, zero, negative = find_peaks_and_zero_crossings(df)
    targ_max = 0.000024

    im_col = df["Im"]
    im_colPositive = im_col[0:positive]
    im_colNegative = im_col[zero:negative]

    if len(im_colPositive) == 0 or len(im_colNegative) == 0:
        # A peak at the first point leaves no branch to analyze.
        print("[analysis] cv_interpret: no usable anodic/cathodic branch, recording NaN")
        return (float("nan"), float("nan"), float("nan"))

    vf_col = df["Vf"]
    vf_colPositive = vf_col[0:positive]
    vf_colNegative = vf_col[zero:negative]

    min_idx_pos = (im_colPositive - targ_max).abs().idxmin()
    vf_max = vf_colPositive.loc[min_idx_pos]

    min_idx_neg = (im_colNegative + targ_max).abs().idxmin()
    vf_min = vf_colNegative.loc[min_idx_neg]

    return (vf_max - vf_min, vf_max, vf_min)


# =====================================================================
# CA / CP interpretation
# =====================================================================

def cp_interpret(filename):
    """Run CV analysis under the CA/CP alias."""
    return cv_interpret(filename)

ca_interpret = cp_interpret


# =====================================================================
# Capacitance interpretation
# =====================================================================

def capacitance_interpret(cycles, target_voltage=None, voltage_col="Vf",
                          current_col="Im", current_units="A"):
    """Estimate capacitance (mF) from CV cycles keyed by scan rate (mV/s).

    Use one full cycle per rate and at least two rates, with currents in A
    or mA. The target defaults to the first cycle's voltage midpoint.
    Fits pass through zero. Return branch and average capacitance, R² values,
    target voltage, and sampled points."""
    scale = 1000.0 if current_units == "A" else 1.0
    rows = []

    for rate, df in sorted(cycles.items()):
        v = df[voltage_col].reset_index(drop=True)
        i = df[current_col].reset_index(drop=True) * scale     # mA

        if target_voltage is None:
            target_voltage = (v.max() + v.min()) / 2

        mid = v.idxmax()                                       # anodic -> cathodic turn
        v_ano, i_ano = v.loc[:mid], i.loc[:mid]
        v_cat, i_cat = v.loc[mid:], i.loc[mid:]

        idx_ano = (v_ano - target_voltage).abs().idxmin()
        idx_cat = (v_cat - target_voltage).abs().idxmin()

        rows.append({
            "Scan Rate (mV/s)": rate,
            "Anodic V (V)": float(v_ano.loc[idx_ano]),
            "Anodic Current (mA)": float(i_ano.loc[idx_ano]),
            "Cathodic V (V)": float(v_cat.loc[idx_cat]),
            "Cathodic Current (mA)": float(i_cat.loc[idx_cat]),
        })

    points = pd.DataFrame(rows)
    if len(points) < 2:
        raise ValueError("capacitance_interpret needs cycles at >= 2 scan rates")

    x = points["Scan Rate (mV/s)"].to_numpy(dtype=float)

    def _zero_intercept_fit(y):
        slope = float(np.sum(x * y) / np.sum(x * x))
        y_hat = slope * x
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
        return slope, r2

    cap_ano, r2_ano = _zero_intercept_fit(np.abs(points["Anodic Current (mA)"].to_numpy()))
    cap_cat, r2_cat = _zero_intercept_fit(np.abs(points["Cathodic Current (mA)"].to_numpy()))
    # slope units: mA / (mV/s) = F

    return {
        "capacitance_anodic_mF": cap_ano * 1000,
        "capacitance_cathodic_mF": cap_cat * 1000,
        "capacitance_avg_mF": (cap_ano + cap_cat) / 2 * 1000,
        "r2_anodic": r2_ano,
        "r2_cathodic": r2_cat,
        "target_voltage": float(target_voltage),
        "points": points,
    }


# =====================================================================
# BUMPS fitting engine (was BUMPS.py)
# =====================================================================

class BUMPS():

    def __init__(self):
        if not HAVE_BUMPS:
            raise ImportError("bumps/dill are required for BUMPS fitting -- pip install bumps dill")
        self.models = list()
        self.functions = list()
        self.parameters = list()
        self.settings = {'dream': {'samples': 2500, 'burn': 1000, 'population': 10, 'thinning': 1}}

    def addfunction(self, function, pars):
        self.functions.append(function)
        self.parameters.append(pars)

    def addmodel(self, x, y, dy, index=-1):
        try:
            function = self.functions[index]
            parameters = self.parameters[index]
        except ValueError:
            print('Function or Parameter list are empty')

        details = inspect.signature(function)
        self.models.append(bmp.Curve(function, x, y, dy))

        for key in details.parameters:
            p = getattr(self.models[index], key)
            for par in parameters:
                if par.name == key:
                    setattr(self.models[index], key, par)

    def setproblem(self, models):
        self.problem = bmp.FitProblem(models)

    def fitproblem(self, method='dream'):
        d = self.settings[method]
        self.result, self.obj = fit(self.problem,
                                    method='dream',
                                    burn=d['burn'],
                                    pop=d['population'],
                                    init='eps',
                                    thin=d['thinning'],
                                    steps=d['steps'],
                                    store='test',
                                    verbose=False)

    def getparameters(self):
        d = {}
        for i, model in enumerate(self.models):
            problem = self.problem
            result = self.result
            d[i] = {}
            d[i]['label'] = []
            d[i]['par'] = []
            d[i]['par_err'] = []

            for key in problem.model_parameters()['models'][i].keys():
                count = 0
                for j, l in enumerate(problem.labels()):
                    if l == key:
                        d[i]['label'].append(key)
                        d[i]['par'].append(result.x[j])
                        d[i]['par_err'].append(result.dx[j])
                        count += 1

            if (count != 1):
                d[i]['label'].append(key)
                d[i]['par'].append(problem.model_parameters()['models'][i][key].value)
                d[i]['par_err'].append(0)

        return d

    def savefitresult(self, fname='save.xlsx'):
        d = {}
        pars = self.getparameters()
        for i, model in enumerate(self.models):
            p = []
            for par in self.parameters[i]:
                p.append(par.value)

            f = model.fn
            d['model_%d' % (i)] = {}
            d['model_%d' % (i)]['x'] = model.x
            d['model_%d' % (i)]['y'] = model.y
            d['model_%d' % (i)]['y_fit'] = f(model.x, *p)
            d['model_%d' % (i)]['dy'] = model.dy
            d['model_%d' % (i)]['par_labels'] = pars[i]['label']
            d['model_%d' % (i)]['par_vals'] = pars[i]['par']
            d['model_%d' % (i)]['par_err'] = pars[i]['par_err']

            writer = pd.ExcelWriter(fname, engine='xlsxwriter')
            for key in d.keys():
                df = pd.DataFrame.from_dict(d[key], orient='index').T
                df.to_excel(writer, sheet_name=key)
            writer.close()
        return d

    def save(self):
        return dill.dumps(self)

    def load(self, obj):
        self.__dict__.update(dill.loads(obj).__dict__)

    # Optional fit plot.
    # def plotfit(self, style='log-log'):
    #     plt.figure(figsize=(3, 3), dpi=300)
    #     colors = ['r', 'b', 'g', 'c', 'k']
    #     for i, model in enumerate(self.models):
    #         x, y, dy = model.x, model.y, model.dy
    #         f = model.fn
    #         p = [par.value for par in self.parameters[i]]
    #         plt.errorbar(x, y, yerr=dy, linestyle='', marker='o',
    #                      label='data_%d' % (i + 1), markersize=1, c=colors[i])
    #         plt.plot(x, f(x, *p), linestyle='-', c=colors[i])
    #     plt.xlabel('x')
    #     plt.ylabel('y')
    #     if ('log' in style):
    #         plt.xscale('log')
    #         plt.yscale('log')
    #     plt.legend()
    #     plt.show()


# =====================================================================
# PEIS circuit fitting (DataAnalyzer)
# =====================================================================

class DataAnalyzer():

    def __init__(self, csv_path):
        self.bump = BUMPS()
        self.data = pd.read_csv(csv_path, sep=",")
        self.ReZ_data_1 = self.data['zreal']
        self.f_data1 = self.data['freq']
        self.ImZ_data_1 = -self.data["zimag"]

        # Alternative Biologic columns:
        # ReZ_data_1 = data['Re(Z)/Ohm']; f_data1 = data['freq/Hz']; ImZ_data_1 = data[" -Im(Z)/Ohm"]
        self.minR = self.ReZ_data_1[np.argmin(self.ImZ_data_1)]

    def impedance(self, x, R1, R2, R3, alpha1, alpha2, sigma1, sigma2):
        w = 2 * np.pi * x
        Z1 = sigma1 * ((1j * w) ** alpha1)
        Z2 = sigma2 * ((1j * w) ** alpha2)
        RC1 = 1 / (1 / (R1) + Z1)
        RC2 = 1 / (1 / (R2) + Z2)
        Rf = R3 + RC1 + RC2
        return Rf

    def impedance1(self, x, R1, R2, alpha1, sigma1):
        w = 2 * np.pi * x
        RC2 = 1 / (1 / R2 + sigma1 * ((1j * w) ** alpha1))
        Rf = R1 + RC2
        return Rf

    def Zreal(self, x, R1, R2, R3, alpha1, alpha2, sigma1, sigma2):
        return self.impedance(x, R1, R2, R3, alpha1, alpha2, sigma1, sigma2).real

    def Zimag(self, x, R1, R2, R3, alpha1, alpha2, sigma1, sigma2):
        return -(self.impedance(x, R1, R2, R3, alpha1, alpha2, sigma1, sigma2).imag)

    def Zreal1(self, x, R1, R2, alpha1, sigma1):
        return self.impedance1(x, R1, R2, alpha1, sigma1).real

    def Zimag1(self, x, R1, R2, alpha1, sigma1):
        return -(self.impedance1(x, R1, R2, alpha1, sigma1).imag)

    def fit_model(self, x, Zr, Zi, fname, steps):
        y1 = Zr
        dy1 = np.abs(Zr)
        y2 = np.abs(Zi)
        dy2 = np.abs(Zi)

        params1 = [bmp.Parameter(name="R1", value=self.minR).range(1, np.inf),
                   bmp.Parameter(name="R2", value=self.minR * 1000).range(1, np.inf),
                   bmp.Parameter(name="alpha1", value=.5).range(0, 1),
                   bmp.Parameter(name="sigma1", value=1e-6).range(0, 1)]

        params = [bmp.Parameter(name="R1", value=self.minR * 100).range(0, np.inf),
                  bmp.Parameter(name="R2", value=self.minR * 100000).range(0, np.inf),
                  bmp.Parameter(name="R3", value=self.minR).range(1, np.inf),
                  bmp.Parameter(name="alpha1", value=.5).range(0, 1),
                  bmp.Parameter(name="alpha2", value=.5).range(0, 1),
                  bmp.Parameter(name="sigma1", value=1e-6).range(0, 1),
                  bmp.Parameter(name="sigma2", value=1e-6).range(0, 1)]

        for i in range(len(Zr)):
            dy1[i] *= 0.05
            dy2[i] *= 0.05

        self.bump.addfunction(self.Zreal1, params1)
        self.bump.addmodel(x, y1, dy1)
        self.bump.addfunction(self.Zimag1, params1)
        self.bump.addmodel(x, y2, dy2)

        self.bump.setproblem(self.bump.models)
        self.bump.settings['dream']['steps'] = steps

        self.bump.fitproblem()
        obj = self.bump.obj

        self.bump.savefitresult(fname=fname)
        return self.bump, obj

    def imp(self, fdata, Zrdata, Zimgdata):
        f = fdata
        Zp = Zrdata
        Zpp = []
        for i in range(len(Zimgdata)):
            Zpp.append(-Zimgdata[i])

        Z = []
        Y = []
        for i in range(len(Zimgdata)):
            Z.append(Zp[i] + 1j * Zpp[i])
            Y.append(1 / Z[i])

        return np.asarray(f), np.asarray(Z)

    def run(self, fname):
        # More DREAM steps increase fitting time.
        f_d, Z_d = self.imp(self.f_data1, self.ReZ_data_1, self.ImZ_data_1)

        mask = (Z_d.real > 0) & (-Z_d.imag > 20)
        self.bump, obj = self.fit_model(f_d[mask], Z_d[mask].real, -Z_d[mask].imag,
                                        fname='res/bumps/' + fname + ".xlsx", steps=5000)
        return obj

        # Optional fit overlay:
        # p = bump.getparameters()[0]['par']
        # fit_ZR = bump.models[0].fn(f_d[mask], *p)
        # fit_ZI = bump.models[1].fn(f_d[mask], *p)
        # fig, ax = plt.subplots(1, 1, figsize=(6, 6))
        # ax.plot(Z_d.real[mask], -Z_d.imag[mask], marker='o', linestyle='',
        #         mec='#005162', mfc='None', markersize=5)
        # ax.plot(fit_ZR, fit_ZI, marker='', linestyle='-', color='k', linewidth=2)
        # plt.xlabel("Z Real (Ohm)")
        # plt.ylabel("-Z Imaginary (Ohm)")
        # plt.show()


# =====================================================================
# Plotting helpers; older examples remain commented out.
# =====================================================================

# --- PEIS intercept / Nyquist plot ---
# def plot_peis_intercept(source, title="Nyquist"):
#     res = eis_interpret(source)
#     df = _as_df(source)
#     if "reflected_zimag" not in df.columns:
#         df = df.copy()
#         df["reflected_zimag"] = [-v for v in df["zimag"]]
#     fig, ax = plt.subplots(figsize=(6, 6))
#     ax.scatter(df["zreal"], df["reflected_zimag"], marker='.', color='b')
#     ax.axhline(y=0, color='k', linestyle=':')
#     ax.plot(res["minima_zreal"], res["reflected_zimag"], 'rx', markersize=10,
#             label=f"intercept ~ {res['minima_zreal']:.2f} ohm")
#     ax.set_xlabel('Zreal (ohm)')
#     ax.set_ylabel('-Zimag (ohm)')
#     ax.set_title(title)
#     ax.legend()
#     plt.tight_layout()
#     plt.show()

# Set to False to skip all test plots; analysis CSVs are still saved.
GRAPHS_ENABLED = True

# GRAPH BEGIN ---------------------------------------------------------
def _graphs_ok():
    if not GRAPHS_ENABLED:
        print("[analysis] graphs disabled (GRAPHS_ENABLED=False)")
        return False
    if plt is None:
        print("[analysis] matplotlib not available -- graphs skipped")
        return False
    return True


def plot_capacitance_cycles(cycles, voltage_col="Vf", current_col="Im"):
    """Plot one CV cycle per scan rate, with current in mA."""
    if not _graphs_ok():
        return None
    fig, ax = plt.subplots(figsize=(6, 4))
    for rate, df in sorted(cycles.items()):
        ax.plot(df[voltage_col], df[current_col] * 1000, label=f"{rate} mV/s")
    ax.set_xlabel("Potential (V)")
    ax.set_ylabel("Current (mA)")
    ax.legend(title="Scan rate")
    fig.tight_layout()
    plt.show()
    return fig


def plot_capacitance_fit(result, title=""):
    """Plot anodic and cathodic current against scan rate with fitted lines."""
    if not _graphs_ok():
        return None
    pts = result["points"]
    x = pts["Scan Rate (mV/s)"]
    fig, ax = plt.subplots(figsize=(6, 4))
    for branch, color in (("Anodic", "red"), ("Cathodic", "blue")):
        y = pts[f"{branch} Current (mA)"].abs()
        cap_mF = result[f"capacitance_{branch.lower()}_mF"]
        r2 = result[f"r2_{branch.lower()}"]
        ax.scatter(x, y, label=branch, color=color)
        ax.plot(x, (cap_mF / 1000) * x, color=color, linestyle="--",
                label=f"{branch} Fit: slope={cap_mF:.4f} mF, R²={r2:.4f}")
    ax.set_title(f"Cap Fit - {title}" if title else "Cap Fit")
    ax.set_xlabel("Scan Rate (mV/s)")
    ax.set_ylabel("Current (mA)")
    ax.legend()
    fig.tight_layout()
    plt.show()
    return fig
def save_capacitance_graphs(cycles, result, out_base,
                            voltage_col="Vf", current_col="Im"):
    """Save <out_base>_cycles.png and, if a fit is available, _fit.png.

    Uses an Agg canvas for GUI worker threads. Returns paths, or None if
    graphs are disabled, matplotlib is unavailable, or saving fails."""
    if not _graphs_ok():
        return None
    try:
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        paths = []
        fig = Figure(figsize=(6, 4))
        FigureCanvasAgg(fig)                 # Explicit canvas for older matplotlib versions.
        ax = fig.add_subplot(111)
        for rate, df in sorted(cycles.items()):
            ax.plot(df[voltage_col], df[current_col] * 1000, label=f"{rate} mV/s")
        ax.set_xlabel("Potential (V)")
        ax.set_ylabel("Current (mA)")
        ax.legend(title="Scan rate")
        fig.tight_layout()
        p = out_base + "_cycles.png"
        fig.savefig(p, dpi=150)
        paths.append(p)

        pts = None if result is None else result["points"]
        if pts is not None:      # Without a fit, save only the cycles.
            x = pts["Scan Rate (mV/s)"]
            fig2 = Figure(figsize=(6, 4))
            FigureCanvasAgg(fig2)
            ax2 = fig2.add_subplot(111)
            for branch, color in (("Anodic", "red"), ("Cathodic", "blue")):
                y = pts[f"{branch} Current (mA)"].abs()
                cap_mF = result[f"capacitance_{branch.lower()}_mF"]
                r2 = result[f"r2_{branch.lower()}"]
                ax2.scatter(x, y, label=branch, color=color)
                ax2.plot(x, (cap_mF / 1000) * x, color=color, linestyle="--",
                         label=f"{branch} Fit: slope={cap_mF:.4f} mF, R²={r2:.4f}")
            ax2.set_title(f"Cap Fit - {Path(out_base).name}")
            ax2.set_xlabel("Scan Rate (mV/s)")
            ax2.set_ylabel("Current (mA)")
            ax2.legend()
            fig2.tight_layout()
            p = out_base + "_fit.png"
            fig2.savefig(p, dpi=150)
            paths.append(p)
        print("[analysis] capacitance graphs saved: " + ", ".join(paths))
        return paths
    except Exception as e:
        print(f"[analysis] capacitance graph save failed (run data unaffected): {e!r}")
        return None
def save_capacitance_graphs_from_df(df, out_base, target_voltage=None,
                                    voltage_col="Vf", current_col="Im",
                                    write_points_csv=True):
    """Analyze cycles grouped by scan_rate_mV_s and save their plots.

    With at least two rates, optionally save _points.csv even when graphs
    are disabled. Pass the configured target_voltage to match the run.
    Returns plot paths, or None if plots are skipped or an error occurs."""
    try:
        if "scan_rate_mV_s" not in getattr(df, "columns", []):
            print("[analysis] combined df has no scan_rate_mV_s column -- capacitance analysis skipped")
            return None
        cycles = {r: g.reset_index(drop=True) for r, g in df.groupby("scan_rate_mV_s")}
        result = None
        if len(cycles) >= 2:
            result = capacitance_interpret(cycles, target_voltage=target_voltage,
                                           voltage_col=voltage_col,
                                           current_col=current_col,
                                           current_units="A")
            if write_points_csv:
                pts = result["points"].copy()
                pts["cap_anodic_mF"] = result["capacitance_anodic_mF"]
                pts["cap_cathodic_mF"] = result["capacitance_cathodic_mF"]
                pts["cap_avg_mF"] = result["capacitance_avg_mF"]
                pts["r2_anodic"] = result["r2_anodic"]
                pts["r2_cathodic"] = result["r2_cathodic"]
                pts["target_V"] = result["target_voltage"]
                pts.to_csv(out_base + "_points.csv", index=False)
                print("[analysis] capacitance points saved: " + out_base + "_points.csv")
        return save_capacitance_graphs(cycles, result, out_base,
                                       voltage_col=voltage_col, current_col=current_col)
    except Exception as e:
        print(f"[analysis] capacitance analysis failed (run data unaffected): {e!r}")
        return None
_GRAPH_COLS = {
    # Test -> (x columns, y columns, x label, y label).
    # Column matching ignores case, spaces, and underscores.
    "PEIS": (("zreal", "z_real"), ("zimag", "z_imag"), "Zreal (ohm)", "-Zimag (ohm)"),
    "CV":   (("vf", "voltage"), ("im", "current"), "Vf (V)", "Im (A)"),
    "CA":   (("time", "t"), ("im", "current"), "time (s)", "Im (A)"),
}


def _find_col_ci(df, candidates):
    lower = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace("_", "")
        if key in lower:
            return lower[key]
    return None


def save_test_graph(df, test, out_base):
    """Save a PEIS, CV, or CA plot to <out_base>.png.

    Respects GRAPHS_ENABLED. Returns the path, or None if skipped or saving
    fails. Capacitance plots use save_capacitance_graphs_from_df."""
    if not _graphs_ok():
        return None
    try:
        kind = str(test).upper()
        spec = _GRAPH_COLS.get(kind)
        if spec is None:
            print(f"[analysis] no graph spec for test {test!r} -- skipped")
            return None
        xc_cands, yc_cands, xlab, ylab = spec
        xc = _find_col_ci(df, xc_cands)
        yc = _find_col_ci(df, yc_cands)
        if not xc or not yc:
            print(f"[analysis] {test}: plot columns not found in {list(df.columns)} -- skipped")
            return None
        from matplotlib.figure import Figure
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        x = df[xc].astype(float)
        y = df[yc].astype(float)
        if kind == "PEIS":
            y = -y                                       # reflected -Zimag
        fig = Figure(figsize=(6, 4))
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.plot(x, y, "o-" if kind == "PEIS" else "-", markersize=3)
        if kind == "PEIS":
            ax.axhline(y=0, color="k", linestyle=":")
            nn = y >= 0                                  # same math as eis_interpret
            if nn.any():
                xi = float(x[nn].loc[y[nn].idxmin()])
                ax.plot([xi], [0], "rx", markersize=9,
                        label=f"x-intercept = {xi:.3f} ohm")
                ax.legend()
        ax.set_xlabel(xlab)
        ax.set_ylabel(ylab)
        ax.set_title(Path(out_base).name)
        fig.tight_layout()
        p = out_base + ".png"
        fig.savefig(p, dpi=150)
        print("[analysis] graph saved: " + p)
        return p
    except Exception as e:
        print(f"[analysis] {test} graph save failed (run data unaffected): {e!r}")
        return None
# GRAPH END -----------------------------------------------------------

# Legacy live plotters from UniversalGraph.py, replaced by the GUI datafeed.
# def plotOCV(curve, data, fig, ax):
#     plt.cla()
#     plt.title("Open Current Voltage")
#     ax.set_ylabel('vf'); ax.set_xlabel('time')
#     ax.scatter(data['time'][7:], data['vf'][7:], marker='.')
#     plt.tight_layout(); fig.canvas.draw()
#
# def plotCA(curve, data, fig, ax):
#     plt.cla()
#     ax.set_xlabel('Time(S)'); ax.set_ylabel('Current')
#     ax.scatter(data['time'][1:], data['current'][1:], marker='.')
#     plt.tight_layout(); fig.canvas.draw()
#
# def plotCV(curve, data, ScanRate, ScanRates, ScanNumber, ScanDelay, data_frame, fig, ax):
#     plt.cla()
#     ax.set_xlabel('E vs Eref (V)'); ax.set_ylabel('Current (A)')
#     ax.scatter(data['vf'][1:], data['im'][1:], marker='.', label=ScanRate)
#     for i in range(ScanNumber):
#         ax.scatter(data_frame[i]['vf'], data_frame[i]['im'], marker='.', label=ScanRates[i])
#     plt.legend(loc='upper left', title="Scan Rate (V/s)")
#     plt.tight_layout(); fig.canvas.draw()
#
# def plotEIS(ax, fig, Zreal_list, Zimag_list, Zreal, Zimag, PlotTitle):
#     plt.cla()
#     ax.set_xlabel('Zreal (ohm)'); ax.set_ylabel('-Zimag (ohm)')
#     ax.scatter(Zreal_list, Zimag_list, marker='.', color='b')
#     ax.axhline(y=0, color='k', linestyle=':')
#     plt.title(PlotTitle)
#     plt.tight_layout(); fig.canvas.draw()