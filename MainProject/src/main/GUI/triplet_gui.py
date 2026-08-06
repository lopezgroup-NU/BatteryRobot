#NOTE: include live x-intercept calculation? or add it at the end of the PEIS live graph.


import ast
import csv
import inspect
import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from utils.PStat import triplet  # same module object BatteryRobotUtils star-imports
except ImportError:
    import triplet  # fallback when run directly from utils/PStat

RUNNER_MODS = {}
for _name in ("peis", "cv", "ca"):
    try:
        RUNNER_MODS[_name] = __import__("utils.PStat." + _name, fromlist=[_name])
    except ImportError:
        try:
            RUNNER_MODS[_name] = __import__(_name)
        except ImportError:
            pass

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    MPL_OK = True
except ImportError:
    MPL_OK = False

ROWS = 6
COLS = 4
COL_LETTERS = ["A", "B", "C", "D"]  # plate columns run A-D left->right (no Excel mirror)
N_MUX = 3

LIVE_ROUTES = {}  # worker thread ident -> Queue receiving (x, y) points


def _live_hook(kind, x, y):
    """Installed as LIVE_HOOK on peis/cv/ca; routes by the thread running the test."""
    try:
        q = LIVE_ROUTES.get(threading.get_ident())
        if q is not None:
            q.put((float(x), float(y)))
    except Exception:
        pass


for _m in RUNNER_MODS.values():
    if _m is not None:
        _m.LIVE_HOOK = _live_hook


def mux_of(i, j):
    return (i * 4 + j) // 8  # rows 1-2 -> mux0, 3-4 -> mux1, 5-6 -> mux2


def _find_col(df, candidates):
    lower = {c.lower().replace(" ", "").replace("_", ""): c for c in df.columns}
    for cand in candidates:
        key = cand.lower().replace("_", "")
        if key in lower:
            return lower[key]
    return None


AXES = {
    "PEIS": ("Zreal (ohm)", "-Zimag (ohm)"),
    "CV": ("Vf (V)", "Im (A)"),
    "CA": ("time (s)", "Im (A)"),
}
FINAL_COLS = {
    "PEIS": (["zreal", "z_real"], ["zimag", "z_imag"]),
    "CV": (["vf", "voltage"], ["im", "current"]),
    "CA": (["time", "t"], ["im", "current"]),
}


class RunPopup:
    """One per run instance; live points stream in, final curve drawn on finish.
    Stays open until manually closed."""
    _count = 0

    def __init__(self, parent, title, kind, route_q):
        self.kind = kind
        self.q = route_q
        self.xs = []
        self.ys = []
        self.finished = False
        self.win = tk.Toplevel(parent)
        self.win.title(title)
        RunPopup._count += 1
        n = RunPopup._count
        self.win.geometry("+{}+{}".format(60 + (n % 5) * 60, 60 + (n % 4) * 50))

        if MPL_OK:
            fig = Figure(figsize=(5.2, 3.6), dpi=100)
            self.ax = fig.add_subplot(111)
            xlab, ylab = AXES.get(kind, ("x", "y"))
            self.ax.set_xlabel(xlab)
            self.ax.set_ylabel(ylab)
            self.ax.set_title(title)
            style = "o-" if kind == "PEIS" else "-"
            self.line, = self.ax.plot([], [], style, markersize=3)
            self.canvas = FigureCanvasTkAgg(fig, master=self.win)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.canvas.draw()
        else:
            self.ax = None
            self.info = tk.Label(self.win, text="matplotlib not installed - live values only")
            self.info.pack(padx=10, pady=10)

        self.status = tk.StringVar(master = self.win, value = "running ...")
        tk.Label(self.win, textvariable=self.status, anchor=tk.W).pack(fill=tk.X)
        self._poll()

    def _alive(self):
        try:
            return self.win.winfo_exists()
        except tk.TclError:
            return False

    def _redraw(self):
        if self.ax is None:
            if self.xs:
                self.info.config(text="last point: {:.4g}, {:.4g} ({} pts)".format(self.xs[-1], self.ys[-1], len(self.xs)))
            return
        self.line.set_data(self.xs, self.ys)
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

    def _poll(self):
        if self.finished or not self._alive():
            return
        got = False
        try:
            while True:
                x, y = self.q.get_nowait()
                self.xs.append(x)
                self.ys.append(y)
                got = True
        except queue.Empty:
            pass
        if got:
            self.status.set("running ... {} pts".format(len(self.xs)))
            self._redraw()
        if not self.finished:
            self.win.after(250, self._poll)

    def finish(self, df):
        if not self._alive():
            return
        self.finished = True
        if df is None:
            try:
                while True:
                    x, y = self.q.get_nowait()
                    self.xs.append(x)
                    self.ys.append(y)
            except queue.Empty:
                pass
            self.status.set("RUN FAILED - showing live points only")
            self.win.title(self.win.title() + " - FAILED")
            self._redraw()
            return
        xc_cands, yc_cands = FINAL_COLS.get(self.kind, ([], []))
        xc = _find_col(df, xc_cands)
        yc = _find_col(df, yc_cands)
        if xc and yc:
            self.xs = list(df[xc].astype(float))
            ys = df[yc].astype(float)
            self.ys = list(-ys) if self.kind == "PEIS" else list(ys)
            self._redraw()
            self.status.set("complete: {} pts (final data)".format(len(self.xs)))
        else:
            self.status.set("complete ({} live pts); columns not found in output: {}".format(len(self.xs), list(df.columns)))


class PlateSetup:
    """First window: creates the Plate, auto-records the sample log, then opens the grid."""

    def __init__(self, root, holder):
        self.root = root
        self.holder = holder
        root.title("New Plate")
        root.resizable(False, False)

        frame = tk.Frame(root, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        default_tests = ",".join(getattr(triplet, "ACTIVE_TESTS", ["PEIS", "CV", "CA"]))
        self.vars = {}
        fields = [("Plate ID", ""), ("Operator", ""), ("Hypothesis", ""), ("Notes", ""), ("Tests (order)", default_tests)]
        for i, (label, default) in enumerate(fields):
            tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=4)
            e = tk.Entry(frame, width=32)
            e.grid(row=i, column=1, padx=5, pady=4)
            e.insert(0, default)
            self.vars[label] = e

        tk.Button(frame, text="Create Plate \u2192", command=self.create_plate,
                  bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                  padx=15, pady=5).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def create_plate(self):
        pid = self.vars["Plate ID"].get().strip()
        config = {"operator": self.vars["Operator"].get().strip(),
                  "hypothesis": self.vars["Hypothesis"].get().strip(),
                  "notes": self.vars["Notes"].get().strip()}
        if pid:
            plate = triplet.Plate(plate_id=pid, config=config)
        else:
            plate = triplet.Plate(config=config)  # uuid default_factory
        self.holder["plate"] = plate

        rs = getattr(triplet, "record_sample", None)
        if rs is not None:
            try:
                kwargs = {"notes": config["notes"]}
                if "hypothesis" in inspect.signature(rs).parameters:
                    kwargs["hypothesis"] = config["hypothesis"]
                rs(plate.plate_id, plate.created_at, **kwargs)
            except Exception as e:
                print("sample log auto-record failed: {!r}".format(e))

        grid_window = tk.Tk()
        PlateGrid(grid_window, plate, self.vars["Tests (order)"].get(), self.holder)
        self.root.destroy()



class PlateGrid:
    """6x4 cell grid: per-cell label + Run, one worker per MUX (3 concurrent runs max),
    tabbed test settings, CSV save/load, per-run live graph popups."""

    def __init__(self, root, plate, tests_string, holder, filename="config/plate_layout.csv"):
        self.root = root
        self.plate = plate
        self.holder = holder
        self.filename = filename
        self.rows = ROWS
        self.cols = COLS
        self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
        self.popups = []

        root.title("Plate Grid - " + plate.plate_id)
        root.resizable(False, False)

        self.main_frame = tk.Frame(root, padx=10, pady=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        tests_frame = tk.Frame(self.main_frame)
        tests_frame.pack(pady=5, fill=tk.X)
        tk.Label(tests_frame, text="Tests (order):").pack(side=tk.LEFT, padx=5)
        self.tests_entry = tk.Entry(tests_frame, width=20)
        self.tests_entry.pack(side=tk.LEFT, padx=5)
        self.tests_entry.insert(0, tests_string)
        tk.Button(tests_frame, text="Run All", command=self.run_all,
                  bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=10)
        tk.Button(tests_frame, text="Stop Run", command=self.stop_run,
                  bg="#E57373", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(tests_frame, text="Settings", command=self.open_settings).pack(side=tk.LEFT, padx=5)

        self.grid_frame = tk.Frame(self.main_frame)
        self.grid_frame.pack(pady=10)

        self.entries = []
        self.run_buttons = []
        for i in range(self.rows):
            row_entries = []
            row_buttons = []
            for j in range(self.cols):
                if j == 0:
                    tk.Label(self.grid_frame, text=str(i + 1), width=2).grid(row=i + 1, column=0, padx=5)
                if i == 0:
                    tk.Label(self.grid_frame, text=COL_LETTERS[j], width=4).grid(row=0, column=j + 1, padx=5)

                cell = tk.Frame(self.grid_frame, bd=1, relief=tk.GROOVE)
                cell.grid(row=i + 1, column=j + 1, padx=2, pady=2)
                entry = tk.Entry(cell, width=10)
                entry.pack(padx=2, pady=2)
                btn = tk.Button(cell, text="Run", width=8,
                                command=lambda r=i, c=j: self.run_cell(r, c))
                btn.pack(padx=2, pady=2)
                row_entries.append(entry)
                row_buttons.append(btn)
            self.entries.append(row_entries)
            self.run_buttons.append(row_buttons)

        self.default_btn_bg = self.run_buttons[0][0].cget("bg")
        self.ui_q = queue.Queue()
        self.gen = 0  # bumped by Stop Run; stale-generation jobs are skipped
        self.jobs = [queue.Queue() for _ in range(N_MUX)]  # one queue per MUX
        for m in range(N_MUX):
            threading.Thread(target=self._worker, args=(m,), daemon=True).start()
        self._poll_ui()

        button_frame = tk.Frame(self.main_frame)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Load CSV", command=self.load_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Save CSV", command=self.save_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Upsert Mongo", command=self.upsert_mongo).pack(side=tk.LEFT, padx=5)
        # tk.Button(button_frame, text="Analyze Plate", command=self.analyze_plate_now).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="CA Cycle", command=self.ca_cycle).pack(side=tk.LEFT, padx=5)
        file_frame = tk.Frame(self.main_frame)
        file_frame.pack(pady=5, fill=tk.X)
        tk.Label(file_frame, text="Filename:").pack(side=tk.LEFT, padx=5)
        self.filename_entry = tk.Entry(file_frame, width=20)
        self.filename_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.filename_entry.insert(0, self.filename)

        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        tk.Label(self.main_frame, textvariable=self.status_var, bd=1,
                 relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

        self.load_default_csv()

    # ---- running tests ----

    def parse_tests(self):
        raw = self.tests_entry.get().replace(",", " ").split()
        tests = [t.strip().upper() for t in raw if t.strip()]
        valid = list(getattr(triplet, "TEST_RUNNERS", {})) or list(getattr(triplet, "test_types", ("PEIS", "CV", "CA")))
        unknown = [t for t in tests if t not in valid]
        if not tests or unknown:
            messagebox.showerror("Error", "Unknown/empty tests: {}. Available: {}".format(unknown, valid))
            return None
        return tests

    def run_cell(self, i, j):
        tests = self.parse_tests()
        if tests is None:
            return
        m = mux_of(i, j)
        self.run_buttons[i][j].config(bg="#FFF59D")
        self.status_var.set("Queued: {}{} on mux{}".format(i + 1, COL_LETTERS[j], m))
        self.jobs[m].put((i, j, tests, self.gen))

    def run_all(self):
        tests = self.parse_tests()
        if tests is None:
            return
        for i in range(self.rows):
            for j in range(self.cols):
                self.run_buttons[i][j].config(bg="#FFF59D")
                self.jobs[mux_of(i, j)].put((i, j, tests, self.gen))
        self.status_var.set("Queued all 24 cells across 3 muxes")

    def stop_run(self):
        self.gen += 1  # invalidates the running cells' remaining tests
        if getattr(self, "ca_cycle_stop", None) is not None:
            self.ca_cycle_stop.set()

        for q in self.jobs:
            try:
                while True:
                    i, j, _, _ = q.get_nowait()
                    self.run_buttons[i][j].config(bg=self.default_btn_bg)
            except queue.Empty:
                pass
        self.status_var.set("Stopping after current tests ...")

    def analyze_plate_now(self):
        try:
            from triplet_analysis import analyze_plate
        except ImportError:
            self.status_var.set("triplet_analysis.py not found")
            return
        self.status_var.set("Plate analysis running ...")

        def job():
            try:
                analyze_plate(triplet.DATA_DIRECTORY, self.plate.plate_id)
                self._ui(lambda: self.status_var.set(
                    "Plate analysis done -> {}_analysis".format(self.plate.plate_id)))
            except Exception as e:
                self._ui(lambda e=e: self.status_var.set("Plate analysis failed: {!r}".format(e)))
                import traceback
                traceback.print_exc()

        threading.Thread(target=job, daemon=True).start()

    def _ui(self, fn):
        self.ui_q.put(fn)  # worker threads must never touch tkinter directly

    def _poll_ui(self):
            try:
                while True:
                    fn = self.ui_q.get_nowait()
                    try:
                        fn()
                    except Exception:
                        import traceback
                        traceback.print_exc()
            except queue.Empty:
                pass
            self.root.after(100, self._poll_ui)

    def _worker(self, mux):
        while True:
            i, j, tests, gen = self.jobs[mux].get()
            if gen != self.gen:
                self._ui(lambda i=i, j=j: self.run_buttons[i][j].config(bg=self.default_btn_bg))
                continue
            row, col = i + 1, COL_LETTERS[j]
            btn = self.run_buttons[i][j]
            failed = []
            stopped = False
            ident = threading.get_ident()
            for t in tests:
                if gen != self.gen:
                    stopped = True
                    break
                self._ui(lambda t=t, row=row, col=col, mux=mux: self.status_var.set(
                    "mux{}: running {} on {}{} ...".format(mux, t, row, col)))
                route = queue.Queue()
                LIVE_ROUTES[ident] = route
                holder = {}
                title = "{} {}{} {}".format(self.plate.plate_id, row, col, t)
                self._ui(lambda h=holder, title=title, t=t, route=route: h.update(
                    p=self._open_popup(title, t, route)))
                df = None
                try:
                    meas = triplet.measure(self.plate, row, col, t)
                    df = getattr(meas, "data", None) if meas is not None else None
                    if df is None:
                        failed.append(t)  # measure() caught a runner failure internally
                except Exception:
                    failed.append(t)
                    import traceback
                    traceback.print_exc()
                finally:
                    LIVE_ROUTES.pop(ident, None)
                self._ui(lambda h=holder, df=df: h.get("p") and h["p"].finish(df))
            if stopped:
                self._ui(lambda btn=btn, row=row, col=col: (
                    btn.config(bg=self.default_btn_bg),
                    self.status_var.set("Stopped at {}{}".format(row, col))))
            elif failed:
                self._ui(lambda btn=btn, row=row, col=col, bad=",".join(failed): (
                    btn.config(bg="#EF9A9A"),
                    self.status_var.set("{}{} failed: {}".format(row, col, bad))))
            else:
                self._ui(lambda btn=btn, row=row, col=col, ts=",".join(tests): (
                    btn.config(bg="#A5D6A7"),
                    self.status_var.set("Done: {}{} ({})".format(row, col, ts))))

    def _open_popup(self, title, kind, route):
        p = RunPopup(self.root, title, kind, route)
        self.popups.append(p)
        return p

    def ca_cycle(self):
            try:
                d = triplet._resolve_params(self.plate, "CA_CYCLE", None)
            except Exception:
                d = dict(getattr(triplet, "PARAM_DEFAULTS", {}).get("CA_CYCLE", {}))
            if not d:
                self.status_var.set("CA_CYCLE defaults not found - is the triplet.py block pasted in?")
                return
    
            win = tk.Toplevel(self.root)
            win.title("CA Cycle - " + self.plate.plate_id)
            frame = tk.Frame(win, padx=10, pady=10)
            frame.pack(fill=tk.BOTH, expand=True)
    
            fields = [("Voltage (V)", str(d["voltage"])),
                      ("Overall time (h)", str(float(d["overall_time"]) / 3600.0)),
                      ("Interval (s)", str(d["interval"])),
                      ("Sample period (s)", str(d["sample_period"])),
                      ("Idle mode (local/open)", str(d.get("idle_mode", "local")))]
            entries = {}
            for i, (label, default) in enumerate(fields):
                tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=3)
                e = tk.Entry(frame, width=14)
                e.grid(row=i, column=1, padx=5, pady=3)
                e.insert(0, default)
                entries[label] = e
            picker = tk.LabelFrame(frame, text="Cells", padx=6, pady=6)
            picker.grid(row=0, column=2, rowspan=len(fields) + 1, padx=(12, 0), sticky="n")
            checks = {}
            for r in range(ROWS):
                for ci in range(COLS):
                    v = tk.BooleanVar(master = win, value = False)
                    tk.Checkbutton(picker, text = "{}{}".format(r + 1, COL_LETTERS[ci]),
                                   variable = v).grid(row = r, column = ci, sticky = "w")
                    checks[r*4+ci] = v

            def _set_all(val):
                for v in checks.values():
                    v.set(val)
            tk.Button(picker, text="All", width=4,
                      command=lambda: _set_all(True)).grid(row=ROWS, column=0, columnspan=2, pady=(4, 0))
            tk.Button(picker, text="None", width=4,
                      command=lambda: _set_all(False)).grid(row=ROWS, column=2, columnspan=2, pady=(4, 0))
    
            def start():
                if any(t.is_alive() for t in getattr(self, "ca_cycle_threads", [])):
                    messagebox.showerror("Error", "A CA cycle run is already going - Stop Run first")
                    return
                try:
                    params = {
                        "voltage": float(entries["Voltage (V)"].get()),
                        "overall_time": float(entries["Overall time (h)"].get()) * 3600.0,
                        "interval": float(entries["Interval (s)"].get()),
                        "sample_period": float(entries["Sample period (s)"].get()),
                        "idle_mode": entries["Idle mode (local/open)"].get().strip().lower(),
                    }
                except ValueError:
                    messagebox.showerror("Error", "Bad number in one of the fields")
                    return
                if params["idle_mode"] not in ("local", "open"):
                    messagebox.showerror("Error", "Idle mode must be 'local' or 'open'")
                    return
                if params["interval"] < 2 * params["sample_period"]:
                    messagebox.showerror("Error", "Interval must be at least 2x the sample period")
                    return
                cells = [c for c, v in checks.items() if v.get()]
                if not cells:
                    messagebox.showerror("Error", "No cells selected")
                    return
                win.destroy()
    
                by_mux = {}
                for c in cells:
                    by_mux.setdefault(c // 8, []).append(c)
                self.ca_cycle_stop = threading.Event()
                self.ca_cycle_threads = []
                for c in cells:
                    self.run_buttons[c // 4][c % 4].config(bg="#FFF59D")
                self.status_var.set("CA cycle: {} cells on mux {}".format(len(cells), sorted(by_mux)))
                done = {"n": 0, "total": len(by_mux)}
    
                def worker(mi, cs):
                    ident = threading.get_ident()
                    route = queue.Queue()
                    LIVE_ROUTES[ident] = route  # ca.py's LIVE_HOOK streams (elapsed_s, Im) here
                    holder = {}
                    labels = ",".join("{}{}".format(c // 4 + 1, COL_LETTERS[c % 4]) for c in cs)
                    title = "{} mux{} CA cycle ({})".format(self.plate.plate_id, mi, labels)
                    self._ui(lambda h=holder, title=title, route=route: h.update(
                        p=self._open_popup(title, "CA", route)))
                    df = None
                    ok = True
                    msg = "mux{} done".format(mi)
                    try:
                        ms = triplet.run_ca_cycle_mux(self.plate, mi, cs,
                                                      params=params, root=".",
                                                      stop_event=self.ca_cycle_stop)
                        try:  # combined final trace for the popup (per-cell data is in the CSVs)
                            import pandas as pd
                            frames = [m.data for m in ms
                                      if getattr(m, "data", None) is not None and len(m.data)]
                            if frames:
                                df = pd.concat(frames).sort_values("time")
                        except Exception:
                            pass
                    except Exception as e:
                        ok = False
                        msg = "mux{} FAILED: {!r}".format(mi, e)
                        import traceback
                        traceback.print_exc()
                    finally:
                        LIVE_ROUTES.pop(ident, None)
                    self._ui(lambda h=holder, df=df: h.get("p") and h["p"].finish(df))
    
                    def fin(msg=msg, ok=ok, cs=cs):
                        bg = "#A5D6A7" if ok else "#EF9A9A"
                        for c in cs:
                            self.run_buttons[c // 4][c % 4].config(bg=bg)
                        done["n"] += 1
                        tail = " - CA cycle finished" if done["n"] == done["total"] else ""
                        self.status_var.set("CA cycle: {}{}".format(msg, tail))
                    self._ui(fin)
    
                for mi, cs in sorted(by_mux.items()):
                    t = threading.Thread(target=worker, args=(mi, cs), daemon=True,
                                         name="ca_cycle_mux{}".format(mi))
                    t.start()
                    self.ca_cycle_threads.append(t)
    
            tk.Button(frame, text="Start", command=start, bg="#4CAF50", fg="white").grid(
                row=len(fields), column=0, columnspan=2, pady=8)
            win.grab_set()
    


    # ---- settings ----

    def open_settings(self):
        defaults = getattr(triplet, "PARAM_DEFAULTS", None)
        if not defaults:
            self.status_var.set("PARAM_DEFAULTS not found in triplet.py")
            return
        win = tk.Toplevel(self.root)
        win.title("Settings - " + self.plate.plate_id)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._settings_entries = {}
        for test in ("PEIS", "CV", "CA"):
            if test not in defaults:
                continue
            frame = tk.Frame(nb, padx=8, pady=8)
            nb.add(frame, text=test)
            merged = dict(defaults[test])
            merged.update(self.plate.config.get(test.lower() + "_params", {}))
            entries = {}
            for r, (key, val) in enumerate(merged.items()):
                tk.Label(frame, text=key).grid(row=r, column=0, sticky="e", padx=5, pady=3)
                e = tk.Entry(frame, width=36)
                e.grid(row=r, column=1, padx=5, pady=3)
                e.insert(0, repr(val))
                entries[key] = e
            self._settings_entries[test] = entries

        def save():
            bad = []
            for test, entries in self._settings_entries.items():
                parsed = {}
                for key, e in entries.items():
                    raw = e.get().strip()
                    try:
                        parsed[key] = ast.literal_eval(raw)
                    except (ValueError, SyntaxError):
                        if raw.startswith(("[", "{", "(")):
                            bad.append("{} / {}".format(test, key))
                            continue
                        parsed[key] = raw  # plain strings pass through
                if test not in [b.split(" / ")[0] for b in bad]:
                    self.plate.config[test.lower() + "_params"] = parsed
            if bad:
                messagebox.showerror("Error", "Could not parse: {}".format(", ".join(bad)))
                return
            self.status_var.set("Settings saved into plate config")
            win.destroy()

        tk.Button(win, text="Save", command=save, bg="#4CAF50", fg="white").pack(pady=8)
        win.grab_set()

    # ---- mongo ----

    def upsert_mongo(self):
        fn = getattr(triplet, "backfill_plate_data", None)
        if fn is None:
            self.status_var.set("backfill_plate_data not found in triplet.py")
            return
        self.status_var.set("Mongo upsert running ...")

        def job():  # own thread: file reads + network only, never toolkitpy
            try:
                fn(".")
                self._ui(lambda: self.status_var.set("Mongo upsert done (includes plate {})".format(self.plate.plate_id)))
            except Exception as e:
                self._ui(lambda e=e: self.status_var.set("Mongo upsert failed: {!r}".format(e)))
                import traceback
                traceback.print_exc()
        threading.Thread(target = job, daemon = True).start()

    # ---- CSV grid (same behavior as RackEditor) ----

    def load_default_csv(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', newline='') as file:
                    new_data = list(csv.reader(file))
                self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
                for i in range(min(len(new_data), self.rows)):
                    for j in range(min(len(new_data[i]) if i < len(new_data) else 0, self.cols)):
                        self.grid_data[i][j] = new_data[i][j]
                self.update_entry_widgets()
                self.status_var.set("Loaded default file: " + self.filename)
            except Exception as e:
                messagebox.showerror("Error", "Failed to load default file: " + str(e))
                self.status_var.set("Default load failed")
        else:
            self.status_var.set("Default file '{}' not found. Starting with empty grid.".format(self.filename))

    def update_grid_data(self):
        for i in range(self.rows):
            for j in range(self.cols):
                self.grid_data[i][j] = self.entries[i][j].get()

    def update_entry_widgets(self):
        for i in range(self.rows):
            for j in range(self.cols):
                self.entries[i][j].delete(0, tk.END)
                self.entries[i][j].insert(0, self.grid_data[i][j])

    def save_csv(self):
        self.update_grid_data()
        filename = self.filename_entry.get()
        if not filename.endswith('.csv'):
            filename += '.csv'
        try:
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                for row in self.grid_data:
                    writer.writerow(row)
            self.status_var.set("Saved to " + filename)
            return True
        except Exception as e:
            messagebox.showerror("Error", "Failed to save file: " + str(e))
            self.status_var.set("Save failed")
            return False

    def load_csv(self):
        filename = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not filename:
            return
        try:
            with open(filename, 'r', newline='') as file:
                new_data = list(csv.reader(file))
            if len(new_data) != self.rows or any(len(row) != self.cols for row in new_data if row):
                messagebox.showwarning("Warning",
                                       "CSV dimensions don't match grid size ({}x{}). Data will be truncated or padded.".format(self.rows, self.cols))
            self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
            for i in range(min(len(new_data), self.rows)):
                for j in range(min(len(new_data[i]) if i < len(new_data) else 0, self.cols)):
                    self.grid_data[i][j] = new_data[i][j]
            self.update_entry_widgets()
            self.filename_entry.delete(0, tk.END)
            self.filename_entry.insert(0, filename)
            self.status_var.set("Loaded " + filename)
        except Exception as e:
            messagebox.showerror("Error", "Failed to load file: " + str(e))
            self.status_var.set("Load failed")

    def clear_all(self):
        for i in range(self.rows):
            for j in range(self.cols):
                self.entries[i][j].delete(0, tk.END)
                self.grid_data[i][j] = ""
                self.run_buttons[i][j].config(bg = self.default_btn_bg)
        self.status_var.set("Grid cleared")


def new_plate():
    """Use instead of Plate(...): pops the setup GUI, returns the Plate."""
    holder = {}
    root = tk.Tk()
    PlateSetup(root, holder)
    root.mainloop()
    return holder.get("plate")


if __name__ == "__main__":
    new_plate()