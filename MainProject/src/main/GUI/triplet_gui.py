"""triplet_gui.py -- plate GUI for the triplet rig.

Per cell: a notes entry, RUN/STOP (also the status light; right-click opens the
per-test status) and VIEW (live graph, opened on demand).
Top bar: test order, Run All, Stop Run, Settings (with a Debug tab).
Bottom bar: Clear Status, CA Cycle, Mux Cycle (incl. FULL), Log Notes, New Plate.

Threading: worker threads never touch tkinter. They post callables to ui_q,
which the main thread drains every 100 ms. Live points arrive through
LIVE_HOOK (installed on peis/cv/ca) and go into a bounded per-cell buffer.
"""
# TODO: individual machine status lights
# TODO: dev menu somewhere else (Settings -> Debug covers this for now)
# TODO: auto pop up and auto close subwindows
# TODO: Settings -- show times in minutes instead of seconds

import ast
import os
import queue
import threading
import time
import traceback
import tkinter as tk
from tkinter import messagebox, ttk

import pandas as pd

try:
    from utils.PStat import triplet  # same module object BatteryRobotUtils star-imports
except ImportError:
    import triplet  # when run directly from utils/PStat

try:
    from utils.PStat import dataanalysis
except ImportError:
    try:
        import dataanalysis
    except ImportError:
        dataanalysis = None

# Arm fills for Mux Cycle (draw / simulate). If this fails to load (e.g. a typo in
# plate_locations.py) the rest of the GUI still works and Mux Cycle runs "none" only.
try:
    from utils.PStat import plate_robot
except Exception as _e:
    try:
        import plate_robot
    except Exception:
        plate_robot = None
        print("[gui] plate_robot not loaded ({!r}) - Mux Cycle can only run 'none'".format(_e))

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
except Exception:
    MPL_OK = False

ROWS = 6
COLS = 4
COL_LETTERS = ["A", "B", "C", "D"]  # plate columns A-D left to right

# Run / Run All worker threads. 1 = one cell at a time, which keeps the Gamry
# layer on one thread; more is NOT stable with the current toolkitpy.
HARDWARE_WORKERS = 1

# Gap between starting the per-mux lanes: the arm's first round goes in mux
# order and the first pstat opens are staggered. After that the arm serves
# whichever mux asks first.
MUX_LANE_GAP_S = 1.0

# Closing the plate window stops every run and waits for the lanes to leave
# their FullMuxSession (which releases the pstats in GamryCom.exe) before the
# window goes away. A second click on X closes anyway.
CLOSE_POLL_MS = 250
CLOSE_WAIT_S = 30.0  # Ctrl+C path only: how long new_plate() waits before returning

# Pipette handling for draw runs (Mux Cycle dialog):
#   "once"  = one tip for the whole run (PlateArm's own behaviour)
#   "fresh" = a new tip for every cell, dropped right after that cell's fill
TIP_MODES = (("Same", "once"), ("New", "fresh"))
TIP_RACK_SIZE = 48  # BatteryRobot.increment_pip_id wraps back to 0 after 47

# Status colors
C_IDLE = None        # the platform's default button bg, filled in at startup
C_BUSY = "#F2752D"   # running
C_QUEUE = "#FFF59D"  # queued
C_DONE = "#A5D6A7"
C_FAIL = "#EF9A9A"

MAX_BUFFER_POINTS = 40000
VIEW_POLL_MS = 250
VIEW_MAX_DRAWN = 30000

LIVE_ROUTES = {}  # worker thread ident -> object with .push(x, y)


def _live_hook(kind, x, y):
    """Installed as LIVE_HOOK on peis/cv/ca; routes by the thread running the test."""
    try:
        target = LIVE_ROUTES.get(threading.get_ident())
        if target is not None:
            target.push(float(x), float(y))
    except Exception:
        pass


for _m in RUNNER_MODS.values():
    if _m is not None:
        _m.LIVE_HOOK = _live_hook


def mux_of(i, j):
    return (i * 4 + j) // 8  # rows 1-2 -> mux0, 3-4 -> mux1, 5-6 -> mux2


def _cell_label(hw):
    return "{}{}".format(hw // 4 + 1, COL_LETTERS[hw % 4])


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
    "CAPACITANCE": ("Vf (V)", "Im (A)"),   # live overlay of the per-rate CV loops
}
FINAL_COLS = {
    "PEIS": (["zreal", "z_real"], ["zimag", "z_imag"]),
    "CV": (["vf", "voltage"], ["im", "current"]),
    "CA": (["time", "t"], ["im", "current"]),
    "CAPACITANCE": (["vf", "voltage"], ["im", "current"]),
}


def _peis_intercept(xs, ys):
    """Zreal at the smallest non-negative -Zimag (same math as eis_interpret)."""
    best_x = best_y = None
    for x, y in zip(xs, ys):
        if y >= 0 and (best_y is None or y < best_y):
            best_x, best_y = x, y
    return best_x


# ---- pipette modes ----

_FreshTipArm = None
if plate_robot is not None and callable(getattr(getattr(plate_robot, "PlateArm", None), "_draw", None)):
    class _FreshTipArm(plate_robot.PlateArm):  # noqa: F811 (replaces the None above)
        """PlateArm that drops its tip after every cell. PlateArm._draw only picks
        up a tip while _tip is False, so clearing it after the drop gives the next
        cell a new one. Done here so plate_robot.py itself is unchanged."""

        def _draw(self, hw):
            note = super()._draw(hw)
            self.robot.remove_pipette()  # ends at safe_zone, like get_pipette
            self._tip = False
            return "{}, new tip".format(note) if note else "new tip"

        def finish(self):
            note = super().finish()      # the last tip is already off, so it parks
            return "tips dropped" if note == "parked" else note


def _tips_needed(tip_mode, n_cells):
    """Tips a draw run takes from the rack."""
    return n_cells if tip_mode == "fresh" else (1 if n_cells else 0)


def _make_arm(robot, mode, volume, tip_mode):
    """The PlateArm for this run's liquid + pipette choice."""
    if mode == "draw" and tip_mode == "fresh":
        arm = _FreshTipArm(robot, mode, volume)
        if not hasattr(arm, "_tip"):
            raise RuntimeError("this plate_robot.py's PlateArm has no _tip flag")
        return arm
    return plate_robot.PlateArm(robot, mode, volume)


class QueueTarget:
    """LIVE_ROUTES adapter for the CA-cycle popups (queue-fed)."""

    def __init__(self, q):
        self.q = q

    def push(self, x, y):
        self.q.put((x, y))


class CellState:
    """Per-cell run state: history, bounded live buffer, stop handling."""

    def __init__(self):
        self.state = "idle"            # idle / queued / running / done / failed / stopped
        self.stop_event = threading.Event()
        self.history = []              # dicts: test, status, note, df
        self.kind = ""                 # test kind currently feeding the buffer
        self.run_serial = 0            # bumped each test so views know to reset
        self.buffer = []               # (x, y) live points, bounded
        self.final_df = None
        self.lane = None               # FULL mux index while its lane runs

    def push(self, x, y):
        self.buffer.append((x, y))
        if len(self.buffer) > MAX_BUFFER_POINTS:
            del self.buffer[: MAX_BUFFER_POINTS // 2]

    def begin_test(self, kind):
        self.kind = kind
        self.run_serial += 1
        self.buffer = []
        self.final_df = None


class LiveView(tk.Toplevel):
    """Live datafeed window. Two sources:
    - cell mode (VIEW button): reads the cell's buffer; survives test changes.
    - queue mode (CA cycle): drains a route queue; finish(df) draws final data.
    Redraws one reused line; autoscales only when data leaves the axes."""

    _count = 0

    def __init__(self, parent, title, kind, cell=None, route_q=None):
        super().__init__(parent)
        self.cell = cell
        self.q = route_q
        self.kind = kind
        self.xs = []
        self.ys = []
        self.finished = False
        self._serial = cell.run_serial if cell is not None else 0
        self._drawn = 0
        self._bounds = None

        self.title(title)
        LiveView._count += 1
        n = LiveView._count
        self.geometry("+{}+{}".format(60 + (n % 5) * 60, 60 + (n % 4) * 50))

        if MPL_OK:
            fig = Figure(figsize=(5.2, 3.6), dpi=100)
            self.ax = fig.add_subplot(111)
            self._set_axes(kind, title)
            style = "o-" if kind == "PEIS" else "-"
            self.line, = self.ax.plot([], [], style, markersize=3)
            self.canvas = FigureCanvasTkAgg(fig, master=self)
            self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self.canvas.draw()
        else:
            self.ax = None
            self.info = tk.Label(self, text="matplotlib not installed - live values only")
            self.info.pack(padx=10, pady=10)

        self.status = tk.StringVar(master=self, value="waiting for data ...")
        tk.Label(self, textvariable=self.status, anchor=tk.W).pack(fill=tk.X)

        if cell is not None and cell.final_df is not None:  # opened after a finish
            self.finish(cell.final_df, kind=cell.kind)
        self._poll()

    def _alive(self):
        try:
            return self.winfo_exists()
        except tk.TclError:
            return False

    def _set_axes(self, kind, title=None):
        if self.ax is None:
            return
        xlab, ylab = AXES.get(kind, ("x", "y"))
        self.ax.set_xlabel(xlab)
        self.ax.set_ylabel(ylab)
        if title:
            self.ax.set_title(title)

    def _reset(self, kind):
        self.kind = kind
        self.xs = []
        self.ys = []
        self._drawn = 0
        self._bounds = None
        self.finished = False
        if self.ax is not None:
            self.ax.clear()
            self._set_axes(kind)
            style = "o-" if kind == "PEIS" else "-"
            self.line, = self.ax.plot([], [], style, markersize=3)

    def _redraw(self, force_scale=False):
        if self.ax is None:
            if self.xs:
                self.info.config(text="last point: {:.4g}, {:.4g} ({} pts)".format(
                    self.xs[-1], self.ys[-1], len(self.xs)))
            return
        step = max(1, len(self.xs) // VIEW_MAX_DRAWN)
        self.line.set_data(self.xs[::step], self.ys[::step])
        lo_x, hi_x = min(self.xs), max(self.xs)
        lo_y, hi_y = min(self.ys), max(self.ys)
        if force_scale or self._bounds is None or \
                lo_x < self._bounds[0] or hi_x > self._bounds[1] or \
                lo_y < self._bounds[2] or hi_y > self._bounds[3]:
            self.ax.relim()
            self.ax.autoscale_view()
            self._bounds = (lo_x, hi_x, lo_y, hi_y)
        self.canvas.draw_idle()

    def _live_status(self):
        text = "running ... {} pts".format(len(self.xs))
        if self.kind == "PEIS" and self.xs:
            xi = _peis_intercept(self.xs, self.ys)
            if xi is not None:
                text += "   x-int ~ {:.2f} ohm".format(xi)
        self.status.set(text)

    def _poll(self):
        if not self._alive():
            return
        got = False
        if self.cell is not None:
            if self.cell.run_serial != self._serial:      # a new test started
                self._serial = self.cell.run_serial
                self._reset(self.cell.kind)
                self.title(self.title().split(" | ")[0] + " | " + self.cell.kind)
            buf = self.cell.buffer
            if len(buf) > self._drawn:
                new = buf[self._drawn:]
                self._drawn = len(buf)
                self.xs.extend(p[0] for p in new)
                self.ys.extend(p[1] for p in new)
                got = True
            if not self.finished and self.cell.final_df is not None:
                self.finish(self.cell.final_df, kind=self.cell.kind)
        elif self.q is not None and not self.finished:
            try:
                while True:
                    x, y = self.q.get_nowait()
                    self.xs.append(x)
                    self.ys.append(y)
                    got = True
            except queue.Empty:
                pass
        if got and not self.finished:
            self._live_status()
            self._redraw()
        self.after(VIEW_POLL_MS, self._poll)

    def finish(self, df, kind=None, failed=False):
        """Draw the final curve (df may be None on failure -> keep live points)."""
        if not self._alive():
            return
        self.finished = True
        kind = kind or self.kind
        if df is None:
            self.status.set("RUN FAILED - showing live points only" if failed
                            else "stopped - showing live points only")
            if self.xs:
                self._redraw(force_scale=True)
            return
        xc_cands, yc_cands = FINAL_COLS.get(kind, ([], []))
        xc = _find_col(df, xc_cands)
        yc = _find_col(df, yc_cands)
        if xc and yc:
            self.xs = list(df[xc].astype(float))
            ys = df[yc].astype(float)
            self.ys = list(-ys) if kind == "PEIS" else list(ys)
            self._redraw(force_scale=True)
            text = "complete: {} pts (final data)".format(len(self.xs))
            if kind == "PEIS":
                xi = _peis_intercept(self.xs, self.ys)
                if xi is not None:
                    text += "   x-intercept = {:.3f} ohm".format(xi)
                    if self.ax is not None:
                        self.ax.plot([xi], [0], "rx", markersize=9)
                        self.canvas.draw_idle()
            self.status.set(text)
        else:
            # no plottable x/y in the final output (e.g. the Capacitance summary
            # table): keep the live trace on screen
            if self.xs:
                self._redraw(force_scale=True)
            self.status.set("complete - {} live pts kept (final output has no plottable columns)".format(
                len(self.xs)))


class PlateSetup:
    """First window: creates the Plate, records the sample log, then opens the grid."""

    def __init__(self, root, holder):
        self.root = root
        self.holder = holder
        root.title("New Plate")
        root.resizable(False, False)
        frame = tk.Frame(root, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)
        default_tests = ",".join(triplet.ACTIVE_TESTS)
        prev = holder.get("plate")  # New Plate: prefill with the last plate's area
        default_area = (prev.config.get("area_cm2") if prev is not None else None) or 0.25
        self.vars = {}
        fields = [("Plate ID", ""), ("Operator", ""), ("Hypothesis", ""), ("Notes", ""),
                  ("Area (cm²)", "{:g}".format(default_area)),
                  ("Tests (order)", default_tests)]
        for i, (label, default) in enumerate(fields):
            tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=4)
            e = tk.Entry(frame, width=32)
            e.grid(row=i, column=1, padx=5, pady=4)
            e.insert(0, default)
            self.vars[label] = e
        tk.Button(frame, text="Create Plate →", command=self.create_plate,
                  bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                  padx=15, pady=5).grid(row=len(fields), column=0, columnspan=2, pady=10)

    def create_plate(self):
        # validate first so a typo keeps the dialog open; read every entry
        # before the setup widgets are destroyed below
        try:
            area = float(self.vars["Area (cm²)"].get().strip())
        except ValueError:
            area = float("nan")
        if not 0 < area < float("inf"):  # also rejects nan
            messagebox.showerror("Error", "Area (cm²) must be a number above 0.", parent=self.root)
            return
        pid = self.vars["Plate ID"].get().strip()
        tests_string = self.vars["Tests (order)"].get()
        config = {"operator": self.vars["Operator"].get().strip(),
                  "hypothesis": self.vars["Hypothesis"].get().strip(),
                  "notes": self.vars["Notes"].get().strip(),
                  "area_cm2": area}
        if pid:
            plate = triplet.Plate(plate_id=pid, config=config)
        else:
            plate = triplet.Plate(config=config)  # timestamp default
        self.holder["plate"] = plate
        try:
            triplet.record_sample(plate.plate_id, plate.created_at, operator=config["operator"],
                                  hypothesis=config["hypothesis"], notes=config["notes"],
                                  area_cm2=config["area_cm2"])
        except Exception as e:
            print("sample log auto-record failed: {!r}".format(e))
        # reuse the same Tk root for the grid (a second Tk() leaves tkinter
        # without a valid default root, which confuses the IDE's pump)
        for child in list(self.root.winfo_children()):
            child.destroy()
        PlateGrid(self.root, plate, tests_string, self.holder)


class PlateGrid:
    """6x4 cell grid. Run / Run All use HARDWARE_WORKERS worker(s); Mux Cycle
    and FULL run one lane per mux."""

    def __init__(self, root, plate, tests_string, holder):
        self.root = root
        self.plate = plate
        self.holder = holder
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
        # These two vars live here (their checkboxes are in Settings -> Debug):
        # run_cell/run_all snapshot stop_on_fail on the UI thread, and the graph
        # toggle is remembered in plate config.
        self.stop_on_fail = tk.BooleanVar(master=root, value=True)
        self.graphs_var = tk.BooleanVar(
            master=root,
            value=bool(self.plate.config.get(
                "generate_graphs",
                (getattr(dataanalysis, "GRAPHS_ENABLED",
                         getattr(dataanalysis, "CAPACITANCE_GRAPHS", True))
                 if dataanalysis else True))))
        self._apply_graphs()

        self.grid_frame = tk.Frame(self.main_frame)
        self.grid_frame.pack(pady=10)
        self.cells = []        # CellState grid
        self.entries = []      # per-cell notes entries
        self.run_buttons = []  # RUN/STOP, also the status light
        for i in range(ROWS):
            row_states = []
            row_entries = []
            row_run = []
            for j in range(COLS):
                if j == 0:
                    tk.Label(self.grid_frame, text=str(i + 1), width=2).grid(row=i + 1, column=0, padx=5)
                if i == 0:
                    tk.Label(self.grid_frame, text=COL_LETTERS[j], width=4).grid(row=0, column=j + 1, padx=5)
                cell = tk.Frame(self.grid_frame, bd=1, relief=tk.GROOVE)
                cell.grid(row=i + 1, column=j + 1, padx=2, pady=2)
                e = tk.Entry(cell, width=11)
                e.pack(padx=2, pady=1)
                b_run = tk.Button(cell, text="RUN", width=8,
                                  command=lambda r=i, c=j: self.toggle_cell(r, c))
                b_run.pack(padx=2, pady=1)
                b_run.bind("<Button-3>", lambda ev, r=i, c=j: self.show_status(r, c))
                b_view = tk.Button(cell, text="VIEW", width=8,
                                   command=lambda r=i, c=j: self.open_view(r, c))
                b_view.pack(padx=2, pady=1)
                row_states.append(CellState())
                row_entries.append(e)
                row_run.append(b_run)
            self.cells.append(row_states)
            self.entries.append(row_entries)
            self.run_buttons.append(row_run)
        global C_IDLE
        C_IDLE = self.run_buttons[0][0].cget("bg")

        self.ui_q = queue.Queue()
        self.gen = 0  # bumped by Stop Run; jobs from older generations are skipped
        self.jobs = queue.Queue()  # Run / Run All: cells run one at a time
        for w in range(HARDWARE_WORKERS):
            threading.Thread(target=self._worker, args=(w,), daemon=True).start()
        self._poll_ui()

        button_frame = tk.Frame(self.main_frame)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Clear Status", command=self.clear_statuses).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="CA Cycle", command=self.ca_cycle).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Mux Cycle", command=self.mux_cycle).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Log Notes",
                  command=self.log_notes_to_plate_log).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="New Plate", command=self.new_plate_button).pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(master=root)
        self.status_var.set("Ready")
        tk.Label(self.main_frame, textvariable=self.status_var, bd=1,
                 relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

        self._closing = False
        self.holder["grid"] = self   # for new_plate()'s Ctrl+C cleanup
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---- closing: stop + release before the window goes ----

    def _ca_mod(self):
        return getattr(triplet, "_ca_driver", None) or RUNNER_MODS.get("ca")

    def _busy_runs(self):
        """(lane threads alive, cells running, open FULL sessions) -- anything
        that still holds, or is about to release, a pstat."""
        threads = [t for t in getattr(self, "mux_threads", []) + getattr(self, "ca_cycle_threads", [])
                   if t.is_alive()]
        cells = sum(1 for row in self.cells for c in row if c.state == "running")
        ca = self._ca_mod()
        try:  # only a ca.py that has open_sessions() counts sessions
            sessions = len(ca.open_sessions()) if hasattr(ca, "open_sessions") else 0
        except Exception:
            sessions = 0
        return len(threads), cells, sessions

    def _begin_shutdown(self):
        try:
            self.stop_run()
        except Exception:
            traceback.print_exc()

    def _force_release(self):
        ca = self._ca_mod()
        if hasattr(ca, "release_all"):
            try:
                ca.release_all()
            except Exception:
                traceback.print_exc()

    def _on_close(self):
        """Window X: Stop Run, keep Tk pumping until the lanes have left their
        sessions, then close. Clicking X again offers to close anyway."""
        if self._closing:
            n_threads, n_cells, n_sess = self._busy_runs()
            if (n_threads or n_cells or n_sess) and not messagebox.askyesno(
                    "Close anyway?",
                    "Runs are still stopping ({} lane(s), {} running cell(s)).\n\n"
                    "Closing now can leave the pstats locked (ERRAPP_DEVICE_IN_USE) "
                    "until GamryCom.exe is killed. Close anyway?".format(n_threads, n_cells),
                    parent=self.root):
                return
            print("[gui] plate window closed while runs were still stopping")
            self._force_release()
            self._finish_close()
            return
        self._closing = True
        self._begin_shutdown()

        def wait():
            if getattr(self, "_shutdown_done", False):
                return
            n_threads, n_cells, n_sess = self._busy_runs()
            if n_threads or n_cells or n_sess:
                self.status_var.set("Closing: waiting for {} lane(s) / {} running cell(s) to stop "
                                    "and release the pstats ... (X again = close anyway)".format(
                                        n_threads, n_cells))
                self._close_after = self.root.after(CLOSE_POLL_MS, wait)
                return
            self._finish_close()
        wait()

    def _finish_close(self):
        self._shutdown_done = True
        self._closed = True                  # stops _poll_ui rescheduling
        try:
            self.root.after_cancel(self._close_after)
        except Exception:
            pass
        for _ in range(HARDWARE_WORKERS):    # let the Run / Run All worker(s) exit
            self.jobs.put(None)
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def shutdown_blocking(self):
        """Same as the X button, for when mainloop was interrupted (Ctrl+C):
        stop, pump Tk while the lanes stop (up to CLOSE_WAIT_S), then return."""
        if getattr(self, "_shutdown_done", False):
            return
        self._closing = True
        self._begin_shutdown()
        deadline = time.time() + CLOSE_WAIT_S
        while any(self._busy_runs()) and time.time() < deadline:
            try:
                self.root.update()   # lanes post to ui_q; keeps the COM pump alive
            except Exception:
                pass
            time.sleep(0.1)
        if any(self._busy_runs()):
            print("[gui] runs still stopping after {:.0f} s -- wait for them before restarting "
                  "the kernel, or the pstats stay locked".format(CLOSE_WAIT_S))
            self._force_release()
        self._shutdown_done = True

    # ---- per-cell buttons ----

    def toggle_cell(self, i, j):
        cell = self.cells[i][j]
        if cell.state in ("queued", "running"):
            cell.stop_event.set()  # FULL cells have their own event: only this cell stops
            self.run_buttons[i][j].config(text="STOPPING", state=tk.DISABLED)
            self.status_var.set("Stopping {}{} ...".format(i + 1, COL_LETTERS[j]))
        else:
            self.run_cell(i, j)

    def show_status(self, i, j):
        cell = self.cells[i][j]
        win = tk.Toplevel(self.root)
        win.title("{}{} - test status".format(i + 1, COL_LETTERS[j]))
        if not cell.history:
            tk.Label(win, text="No tests run yet.", padx=14, pady=10).pack()
            return
        colors = {"running": C_BUSY, "queued": C_QUEUE, "complete": C_DONE,
                  "failed": C_FAIL, "skipped": C_IDLE, "stopped": C_IDLE}
        for k, rec in enumerate(cell.history):
            row = tk.Frame(win, padx=8, pady=2)
            row.pack(fill=tk.X)
            tk.Label(row, text="{}. {}".format(k + 1, rec["test"]), width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=rec["status"], width=9,
                     bg=colors.get(rec["status"], C_IDLE)).pack(side=tk.LEFT, padx=4)
            if rec.get("note"):
                tk.Label(row, text=rec["note"], anchor="w").pack(side=tk.LEFT, padx=4)

    def open_view(self, i, j):
        cell = self.cells[i][j]
        title = "{} {}{}".format(self.plate.plate_id, i + 1, COL_LETTERS[j])
        for p in self.popups:
            if getattr(p, "cell", None) is cell and p._alive():
                p.lift()
                return
        p = LiveView(self.root, title, cell.kind or "CV", cell=cell)
        self.popups.append(p)

    def _set_cell_ui(self, i, j, state):
        """UI thread only: color + text on the RUN/status button."""
        colors = {"idle": C_IDLE, "queued": C_QUEUE, "running": C_BUSY,
                  "done": C_DONE, "failed": C_FAIL, "stopped": C_IDLE}
        btn = self.run_buttons[i][j]
        btn.config(bg=colors.get(state, C_IDLE))
        if state in ("queued", "running"):
            btn.config(text="STOP", state=tk.NORMAL)
        else:
            btn.config(text="RUN", state=tk.NORMAL)

    # ---- Run / Run All / Stop ----

    def parse_tests(self, raw=None):
        """Test names from `raw` (default: the main Tests entry); CAP -> CAPACITANCE."""
        raw = (self.tests_entry.get() if raw is None else raw).replace(",", " ").split()
        tests = [triplet.canon_test(t) for t in raw if t.strip()]
        valid = list(triplet.TEST_RUNNERS)
        unknown = [t for t in tests if t not in valid]
        if not tests or unknown:
            messagebox.showerror("Error", "Unknown/empty tests: {}. Available: {} "
                                 "(aliases: CAP=CAPACITANCE)".format(unknown, valid))
            return None
        return tests

    def _queue_cell(self, i, j, tests, stop_on_fail):
        cell = self.cells[i][j]
        cell.state = "queued"
        cell.stop_event = threading.Event()
        cell.history = []
        self._set_cell_ui(i, j, "queued")
        self.jobs.put((i, j, tests, self.gen, stop_on_fail))

    def run_cell(self, i, j):
        if self._mux_cycle_running():
            return
        tests = self.parse_tests()
        if tests is None:
            return
        # notes only; a cell gets its plate-log row when it actually starts
        self.log_notes_to_plate_log(auto=True)
        self._queue_cell(i, j, tests, self.stop_on_fail.get())
        self.status_var.set("Queued: {}{}".format(i + 1, COL_LETTERS[j]))

    def run_all(self):
        if self._mux_cycle_running():
            return
        tests = self.parse_tests()
        if tests is None:
            return
        self.log_notes_to_plate_log(auto=True)
        sof = self.stop_on_fail.get()
        for i in range(ROWS):
            for j in range(COLS):
                if self.cells[i][j].state not in ("queued", "running"):
                    self._queue_cell(i, j, tests, sof)
        self.status_var.set("Queued all cells (run one at a time)")

    def stop_run(self):
        self.gen += 1  # invalidates queued jobs
        for e in getattr(self, "full_events", {}).values():
            e.set()    # FULL: every mux's own event (its cells have separate ones)
        if getattr(self, "ca_cycle_stop", None) is not None:
            self.ca_cycle_stop.set()
        for row in self.cells:
            for cell in row:
                if cell.state in ("queued", "running"):
                    cell.stop_event.set()
        try:
            while True:
                i, j = self.jobs.get_nowait()[:2]
                self.cells[i][j].state = "stopped"
                self._set_cell_ui(i, j, "stopped")
        except queue.Empty:
            pass
        self.status_var.set("Stopping after current tests ...")

    def clear_statuses(self):
        for i in range(ROWS):
            for j in range(COLS):
                cell = self.cells[i][j]
                if cell.state in ("queued", "running"):
                    continue  # never clear an active cell
                cell.state = "idle"
                cell.history = []
                self._set_cell_ui(i, j, "idle")
        self.status_var.set("Statuses cleared")

    def new_plate_button(self):
        """Tear this grid down and reopen the New Plate dialog on the same Tk root."""
        busy = any(cell.state in ("queued", "running")
                   for row in self.cells for cell in row)
        if busy or any(t.is_alive() for t in getattr(self, "ca_cycle_threads", []) +
                       getattr(self, "mux_threads", [])):
            messagebox.showerror("Error", "Tests are running - Stop Run first")
            return
        self._closed = True                  # stops _poll_ui rescheduling
        for _ in range(HARDWARE_WORKERS):    # unblock workers so they exit
            self.jobs.put(None)
        for child in list(self.root.winfo_children()):
            child.destroy()                  # also closes any LiveView popups
        PlateSetup(self.root, self.holder)

    # ---- plate log (cell notes) ----

    def log_notes_to_plate_log(self, auto=False, ensure_cells=None):
        """Upsert this plate's cell notes into the plate log CSV
        (triplet.PLATE_LOG_DIRECTORY): one row per (PlateID, Cell Position), note
        in a 'Cell Notes' column kept last. ensure_cells: cell ids that get a row
        even with a blank note (cells as they start running). A non-empty note
        overwrites; a blank one never clears an existing note; other columns are
        never touched; nothing is rewritten without a change. Then the notes are
        mirrored into the plate's meta files (all cells on a manual press, only
        changed cells when auto). auto=True (run starts) is silent when there is
        nothing to do and never pops a dialog, so a log problem can't block a run."""
        path = triplet.PLATE_LOG_DIRECTORY
        cols = list(triplet.PLATE_LOG_COLS)
        notes = {}
        for i in range(ROWS):
            for j in range(COLS):
                txt = self.entries[i][j].get().strip()
                if txt:
                    notes["{}{}".format(i + 1, COL_LETTERS[j])] = txt
        want = set(notes) | set(ensure_cells or [])
        if not want:
            if not auto:
                self.status_var.set("No cell notes to log (all entries empty)")
            return
        try:
            if os.path.exists(path):
                # dtype=str + keep_default_na=False: everything stays a string,
                # blanks stay blank (no 'nan'), numeric-looking IDs still match
                df = pd.read_csv(path, dtype=str, keep_default_na=False)
            else:
                d = os.path.dirname(path)
                if d:
                    os.makedirs(d, exist_ok=True)
                df = pd.DataFrame(columns=cols)
            for c in cols:
                if c not in df.columns:
                    df[c] = ""
            if "Cell Notes" not in df.columns:
                df["Cell Notes"] = ""
            df = df[[c for c in df.columns if c != "Cell Notes"] + ["Cell Notes"]]
            pid = str(self.plate.plate_id)
            added = updated = 0
            changed = []  # cells whose logged note changed -> meta sync
            for cell_id in sorted(want):
                mask = (df["PlateID"] == pid) & (df["Cell Position"] == cell_id)
                if mask.any():
                    if cell_id in notes and \
                            (df.loc[mask, "Cell Notes"] != notes[cell_id]).any():
                        df.loc[mask, "Cell Notes"] = notes[cell_id]
                        updated += int(mask.sum())
                        changed.append(cell_id)
                else:
                    row = {c: "" for c in df.columns}
                    row["PlateID"] = pid
                    row["Cell Position"] = cell_id
                    row["Cell Notes"] = notes.get(cell_id, "")
                    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                    added += 1
                    if cell_id in notes:
                        changed.append(cell_id)
            if added or updated:
                df.to_csv(path, index=False)
        except Exception as e:
            # a mangled CSV must not crash a run start: manual press gets the
            # dialog, auto stays non-modal
            if auto:
                print("[gui] plate log auto-update failed: {!r}".format(e))
                self.status_var.set("Plate log auto-update failed (run continues)")
            else:
                messagebox.showerror("Error", "Could not write the plate log ({}) -- "
                                     "is it open in Excel?\n{}".format(path, e))
            return
        # mirror into the meta files, only after the plate log write succeeded
        meta_note = ""
        if not auto or changed:
            sync = getattr(triplet, "sync_meta_cell_notes", None)
            if sync is None:
                print("[gui] meta notes skipped: the deployed triplet.py has no "
                      "sync_meta_cell_notes -- redeploy it")
            else:
                try:
                    n_meta, meta_errs = sync(self.plate.plate_id,
                                             cell_ids=changed if auto else None)
                except Exception as e:  # sync never raises; belt and braces
                    n_meta, meta_errs = 0, [repr(e)]
                for err in meta_errs:
                    print("[gui] meta note not written: {}".format(err))
                if n_meta or meta_errs:
                    meta_note = ", {} meta file(s) updated".format(n_meta)
                if meta_errs:
                    meta_note += ", {} NOT updated (open in Excel? see shell)".format(len(meta_errs))
        if added or updated or not auto or meta_note:
            self.status_var.set("Plate log: {} row(s) added, {} updated{} -> {}".format(
                added, updated, meta_note, path))

    # ---- UI queue ----

    def _ui(self, fn):
        self.ui_q.put(fn)  # worker threads must never touch tkinter directly

    def _poll_ui(self):
        if getattr(self, "_closed", False):  # grid replaced or window closed
            return
        try:
            while True:
                fn = self.ui_q.get_nowait()
                try:
                    fn()
                except Exception:
                    traceback.print_exc()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_ui)

    # ---- per-test outputs (PNGs / capacitance CSV in the cell folder) ----

    def _measurement_base(self, meas):
        """<cellfolder>/<stem>_<TEST>, built the way write_measurement builds it.
        Returns (base, None) or (None, short_reason); details go to the shell."""
        stem = triplet._stem(self.plate.plate_id, meas.cell_id)
        cell_dir = os.path.join(str(triplet.DATA_DIRECTORY), stem)
        if not os.path.isdir(cell_dir):
            print("[gui] test outputs skipped: expected cell folder not found: {}".format(cell_dir))
            return None, "cell folder not found (see shell)"
        return os.path.join(cell_dir, "{}_{}".format(stem, meas.electrochemical_test)), None

    def _cap_analysis_outputs(self, meas, df):
        """Capacitance points CSV + PNGs next to the measurement. Returns a short
        note for the status popup; never raises."""
        if dataanalysis is None:
            print("[gui] capacitance outputs skipped: dataanalysis import failed at GUI startup")
            return "graphs skipped: dataanalysis import failed"
        fn = getattr(dataanalysis, "save_capacitance_graphs_from_df", None)
        if fn is None:
            print("[gui] capacitance outputs skipped: the deployed dataanalysis.py has no "
                  "save_capacitance_graphs_from_df -- redeploy it")
            return "graphs skipped: old dataanalysis.py deployed"
        base, err = self._measurement_base(meas)
        if base is None:
            return "graphs skipped: " + err
        p = triplet._resolve_params(self.plate, "CAPACITANCE", None)
        tv = p.get("target_voltage")
        if tv is None and "v_low" in p and "v_high" in p:
            tv = (float(p["v_low"]) + float(p["v_high"])) / 2.0
        out = fn(df, base, target_voltage=tv)     # never raises; prints its own log
        folder = os.path.dirname(base) or os.getcwd()
        if out:
            return "graphs -> {}".format(folder)
        return "points csv -> {} (graphs off, <2 rates, or see shell)".format(folder)

    def _test_graph_output(self, meas, df, t):
        """Final-data PNG for a completed PEIS/CV/CA test, in the cell folder.
        Returns a short note for the status popup; never raises."""
        if dataanalysis is None:
            return "graph skipped: dataanalysis import failed"
        fn = getattr(dataanalysis, "save_test_graph", None)
        if fn is None:
            print("[gui] test graph skipped: the deployed dataanalysis.py has no "
                  "save_test_graph -- redeploy it")
            return "graph skipped: old dataanalysis.py deployed"
        base, err = self._measurement_base(meas)
        if base is None:
            return "graph skipped: " + err
        p = fn(df, t, base)                        # never raises; prints its own log
        if p:
            return "graph -> {}".format(os.path.dirname(p))
        return "no graph (off or see shell)"

    def _full_graph(self, measurement, test):
        """The FULL lanes bypass _worker, so they call its PNG step through here
        (on the lane thread). Never raises."""
        try:
            df = getattr(measurement, "data", None)
            if df is None or len(df) == 0:
                return ""
            return self._test_graph_output(measurement, df, test)
        except Exception:
            traceback.print_exc()
            return ""

    # ---- worker (Run / Run All, and each plain Mux Cycle lane) ----

    def _worker(self, worker_id, jobs=None):
        jobs = self.jobs if jobs is None else jobs  # a Mux Cycle lane gets its mux's queue
        while True:
            job = jobs.get()
            if job is None:  # shutdown sentinel
                return
            i, j, tests, gen, stop_on_fail = job[:5]
            fill = job[5] if len(job) > 5 else None  # Mux Cycle: arm fill before the tests
            cell = self.cells[i][j]
            if gen != self.gen or cell.stop_event.is_set():
                cell.state = "stopped" if cell.stop_event.is_set() else "idle"
                self._ui(lambda i=i, j=j, s=cell.state: self._set_cell_ui(i, j, s))
                continue
            row, col = i + 1, COL_LETTERS[j]
            cell.state = "running"
            self._ui(lambda i=i, j=j: self._set_cell_ui(i, j, "running"))
            # only cells that actually start get a plate-log row (via ui_q:
            # the logger reads tk entry widgets)
            self._ui(lambda cid="{}{}".format(row, col): self.log_notes_to_plate_log(
                auto=True, ensure_cells=[cid]))
            failed = []
            stopped = False
            # fill this cell first (waits its turn for the arm); the tests start
            # the moment the fill returns and the arm moves on
            if fill is not None:
                rec = {"test": "FILL", "status": "running", "note": ""}
                cell.history.append(rec)
                self._ui(lambda row=row, col=col, m=mux_of(i, j): self.status_var.set(
                    "filling {}{} (mux{}) ...".format(row, col, m)))
                try:
                    rec["note"] = fill(i * 4 + j, lambda: gen != self.gen or cell.stop_event.is_set()) or ""
                    rec["status"] = "complete" if rec["note"] else "stopped"
                    stopped = not rec["note"]
                except Exception as e:
                    rec["status"] = "failed"
                    rec["note"] = str(e)[:120]
                    failed.append("FILL")
                    print("[gui] {}{} not filled: {}".format(row, col, e))
                if rec["status"] != "complete":
                    for rest in tests:
                        cell.history.append({"test": rest, "status": "skipped", "note": "not filled"})
                    tests = []
            ident = threading.get_ident()
            for k, t in enumerate(tests):
                if gen != self.gen or cell.stop_event.is_set():
                    stopped = True
                    for rest in tests[k:]:
                        cell.history.append({"test": rest, "status": "skipped", "note": "stopped"})
                    break
                self._ui(lambda t=t, row=row, col=col: self.status_var.set(
                    "running {} on {}{} (mux{}) ...".format(t, row, col, mux_of(i, j))))
                rec = {"test": t, "status": "running", "note": ""}
                cell.history.append(rec)
                cell.begin_test(t)
                LIVE_ROUTES[ident] = cell
                df = None
                try:
                    # measure() takes no stop_event, so a cell STOP lands between tests
                    meas = triplet.measure(self.plate, row, col, t)
                    df = getattr(meas, "data", None) if meas is not None else None
                    if cell.stop_event.is_set():
                        rec["status"] = "stopped"
                        stopped = True
                    elif df is None:
                        rec["status"] = "failed"  # measure() caught an internal failure
                        failed.append(t)
                    else:
                        rec["status"] = "complete"
                        try:
                            if t == "CAPACITANCE":
                                rec["note"] = self._cap_analysis_outputs(meas, df)
                            else:
                                rec["note"] = self._test_graph_output(meas, df, t)
                        except Exception:
                            traceback.print_exc()
                except Exception as e:
                    rec["status"] = "failed"
                    rec["note"] = repr(e)[:120]
                    failed.append(t)
                    traceback.print_exc()
                finally:
                    LIVE_ROUTES.pop(ident, None)
                cell.final_df = df
                rec["df"] = df
                if stopped:
                    for rest in tests[k + 1:]:
                        cell.history.append({"test": rest, "status": "skipped", "note": "stopped"})
                    break
                if failed and stop_on_fail:
                    for rest in tests[k + 1:]:
                        cell.history.append({"test": rest, "status": "skipped",
                                             "note": "previous test failed"})
                    break
            if stopped:
                cell.state = "stopped"
                self._ui(lambda i=i, j=j, row=row, col=col: (
                    self._set_cell_ui(i, j, "stopped"),
                    self.status_var.set("Stopped at {}{}".format(row, col))))
            elif failed:
                cell.state = "failed"
                self._ui(lambda i=i, j=j, row=row, col=col, bad=",".join(failed): (
                    self._set_cell_ui(i, j, "failed"),
                    self.status_var.set("{}{} failed: {}".format(row, col, bad))))
            else:
                cell.state = "done"
                self._ui(lambda i=i, j=j, row=row, col=col, ts=",".join(tests): (
                    self._set_cell_ui(i, j, "done"),
                    self.status_var.set("Done: {}{} ({})".format(row, col, ts))))

    def _open_popup(self, title, kind, route):
        p = LiveView(self.root, title, kind, route_q=route)
        self.popups.append(p)
        return p

    def _cell_picker(self, parent, win, rowspan):
        """The 6x4 'Cells' checkbox block (with All / None) used by the CA Cycle
        and Mux Cycle dialogs. Returns {hardware cell 0-23: BooleanVar}."""
        picker = tk.LabelFrame(parent, text="Cells", padx=6, pady=6)
        picker.grid(row=0, column=2, rowspan=rowspan, padx=(12, 0), sticky="n")
        checks = {}
        for r in range(ROWS):
            for ci in range(COLS):
                v = tk.BooleanVar(master=win, value=False)
                tk.Checkbutton(picker, text="{}{}".format(r + 1, COL_LETTERS[ci]),
                               variable=v).grid(row=r, column=ci, sticky="w")
                checks[r * 4 + ci] = v

        def _set_all(val):
            for v in checks.values():
                v.set(val)
        tk.Button(picker, text="All", width=4,
                  command=lambda: _set_all(True)).grid(row=ROWS, column=0, columnspan=2, pady=(4, 0))
        tk.Button(picker, text="None", width=4,
                  command=lambda: _set_all(False)).grid(row=ROWS, column=2, columnspan=2, pady=(4, 0))
        return checks

    # ---- CA Cycle (its own separate flow) ----

    def ca_cycle(self):
        d = triplet._resolve_params(self.plate, "CA_CYCLE", None)

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
        checks = self._cell_picker(frame, win, rowspan=len(fields) + 1)

        def start():
            if self._mux_cycle_running():
                return
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
                messagebox.showerror("Error", "Bad number in one of the fields.")
                return
            if params["idle_mode"] not in ("local", "open"):
                messagebox.showerror("Error", "Idle mode must be 'local' or 'open'.")
                return
            if params["interval"] < 2 * params["sample_period"]:
                messagebox.showerror("Error", "Interval must be at least 2 times the sample period.")
                return
            cells = [c for c, v in checks.items() if v.get()]
            if not cells:
                messagebox.showerror("Error", "No cells selected.")
                return
            win.destroy()
            # every cell in the run gets a plate-log row, note or not
            self.log_notes_to_plate_log(auto=True, ensure_cells=[_cell_label(c) for c in cells])

            by_mux = {}
            for c in cells:
                by_mux.setdefault(c // 8, []).append(c)
            self.ca_cycle_stop = threading.Event()
            self.ca_cycle_threads = []
            for c in cells:
                i, j = c // 4, c % 4
                self.cells[i][j].history.append({"test": "CA_CYCLE", "status": "running", "note": ""})
                self.run_buttons[i][j].config(bg=C_BUSY)
            self.status_var.set("CA cycle: {} cells on mux {}".format(len(cells), sorted(by_mux)))
            done = {"n": 0, "total": len(by_mux)}

            def worker(mi, cs):
                ident = threading.get_ident()
                route = queue.Queue()
                LIVE_ROUTES[ident] = QueueTarget(route)
                holder = {}
                labels = ",".join(_cell_label(c) for c in cs)
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
                    try:  # combined final trace for the popup
                        frames = [m.data for m in ms if getattr(m, "data", None) is not None and len(m.data)]
                        if frames:
                            df = pd.concat(frames).sort_values("time")
                    except Exception:
                        pass
                except Exception as e:
                    ok = False
                    msg = "mux{} FAILED: {!r}".format(mi, e)
                    traceback.print_exc()
                finally:
                    LIVE_ROUTES.pop(ident, None)
                self._ui(lambda h=holder, df=df, ok=ok: h.get("p") and h["p"].finish(df, failed=not ok))

                def fin(msg=msg, ok=ok, cs=cs):
                    bg = C_DONE if ok else C_FAIL
                    status = "complete" if ok else "failed"
                    for c in cs:
                        i, j = c // 4, c % 4
                        self.run_buttons[i][j].config(bg=bg)
                        for rec in self.cells[i][j].history:
                            if rec["test"] == "CA_CYCLE" and rec["status"] == "running":
                                rec["status"] = status
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

    # ---- Mux Cycle (arm fill + test list per cell, one lane per mux; FULL optional) ----

    def _mux_cycle_running(self):
        """True (with an error box) while a Mux Cycle owns the muxes."""
        if any(t.is_alive() for t in getattr(self, "mux_threads", [])):
            messagebox.showerror("Error", "A Mux Cycle is running - Stop Run first")
            return True
        return False

    def mux_cycle(self):
        """Each mux works through its selected cells in channel order on its own
        lane. The arm fills a cell and that cell's tests start right away while
        the arm moves on to the next mux; when a cell's tests end, the arm fills
        that mux's next selected cell. Each test uses its own Settings tab; CA
        hold here is Settings -> CA -> time_run."""
        d = triplet._resolve_params(self.plate, "MUX_CYCLE", None)
        hold = triplet._resolve_params(self.plate, "CA", None).get("time_run", "")

        win = tk.Toplevel(self.root)
        win.title("Mux Cycle - " + self.plate.plate_id)
        frame = tk.Frame(win, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        tests = d.get("tests", ["PEIS", "CV", "CA"])
        entries = {}

        def _field(r, label, default):
            tk.Label(frame, text=label).grid(row=r, column=0, sticky="e", padx=5, pady=3)
            e = tk.Entry(frame, width=16)
            e.grid(row=r, column=1, padx=5, pady=3)
            e.insert(0, default)
            entries[label] = e
            return e
        _field(0, "Tests (order)", tests if isinstance(tests, str) else ", ".join(tests))
        full_var = tk.BooleanVar(master=win, value=bool(d.get("full", False)))
        tk.Checkbutton(frame, text="FULL cycle", variable=full_var).grid(
            row=1, column=1, sticky="w", padx=5, pady=3)
        _field(2, "CA hold (s)", str(hold))
        back_e = _field(3, "CA back (s)", str(d.get("ca_back_s", 60.0)))
        end_e = _field(4, "CA end (s)", str(d.get("ca_end_s", 0.0)))

        def _full_changed(*_):  # CA back / CA end only apply to FULL
            st = tk.NORMAL if full_var.get() else tk.DISABLED
            back_e.config(state=st)
            end_e.config(state=st)
        full_var.trace_add("write", _full_changed)
        _full_changed()

        # liquid handling: draw / simulate / none, with volume and pipette (draw only)
        mode_var = tk.StringVar(master=win, value=str(d.get("liquid_mode", "none")).lower())
        tk.Label(frame, text="Liquid").grid(row=5, column=0, sticky="e", padx=5, pady=3)
        ttk.Combobox(frame, textvariable=mode_var, values=("draw", "simulate", "none"),
                     state="readonly", width=13).grid(row=5, column=1, padx=5, pady=3)
        tk.Label(frame, text="Volume (mL)").grid(row=6, column=0, sticky="e", padx=5, pady=3)
        vol_e = tk.Entry(frame, width=16)
        vol_e.grid(row=6, column=1, padx=5, pady=3)
        vol_e.insert(0, str(d.get("volume_ml", 1.0)))
        tip_labels = dict((v, k) for k, v in TIP_MODES)
        tip_var = tk.StringVar(master=win, value=tip_labels.get(
            str(d.get("tip_mode", "once")).strip().lower(), TIP_MODES[0][0]))
        tk.Label(frame, text="Pipette").grid(row=7, column=0, sticky="e", padx=5, pady=3)
        tip_box = ttk.Combobox(frame, textvariable=tip_var, values=[k for k, _ in TIP_MODES],
                               state="readonly", width=18)
        tip_box.grid(row=7, column=1, padx=5, pady=3)

        def _mode_changed(*_):
            draw = mode_var.get() == "draw"
            vol_e.config(state=tk.NORMAL if draw else tk.DISABLED)
            tip_box.config(state="readonly" if draw else tk.DISABLED)
        mode_var.trace_add("write", _mode_changed)
        _mode_changed()

        checks = self._cell_picker(frame, win, rowspan=9)

        def start():
            busy = any(cell.state in ("queued", "running") for row in self.cells for cell in row)
            if busy or any(t.is_alive() for t in getattr(self, "ca_cycle_threads", []) +
                           getattr(self, "mux_threads", [])):
                messagebox.showerror("Error", "Tests are running - Stop Run first", parent=win)
                return
            tests = self.parse_tests(entries["Tests (order)"].get())
            if tests is None:
                return
            mode = mode_var.get()
            tip_mode = dict(TIP_MODES).get(tip_var.get(), "once")
            try:
                hold = float(entries["CA hold (s)"].get())
                volume = float(vol_e.get())
                back = float(entries["CA back (s)"].get())
                end = float(entries["CA end (s)"].get())
            except ValueError:
                messagebox.showerror("Error", "Bad number in CA hold, CA back, CA end or Volume.", parent=win)
                return
            cells = [c for c, v in checks.items() if v.get()]
            problem = None
            if hold <= 0:
                problem = "CA hold must be above 0 s."
            elif not back >= 0 or back == float("inf"):  # also rejects nan
                problem = "CA back must be 0 s or more (0 = no revisits)."
            elif not end >= 0 or end == float("inf"):
                problem = "CA end must be 0 s or more (0 = off)."
            elif full_var.get() and (tests[-1] != "CA" or len(set(tests)) != len(tests) or
                                     any(t not in ("PEIS", "CV") for t in tests[:-1])):
                problem = ("FULL cycle runs PEIS/CV (optional, any order) then CA, each once, "
                           "e.g. PEIS, CV, CA.")
            elif not cells:
                problem = "No cells selected."
            elif mode != "none":
                if plate_robot is None:
                    problem = "plate_robot.py did not load - see the shell."
                elif plate_robot.get_robot() is None:
                    problem = ("No arm found. Create `rob` in the shell first, or call "
                               "plate_robot.set_robot(<your robot>).")
                elif mode == "draw" and not 0 < volume <= plate_robot.MAX_FILL_ML:
                    problem = "Volume must be above 0 and at most {:g} mL.".format(plate_robot.MAX_FILL_ML)
                elif mode == "draw" and tip_mode == "fresh" and _FreshTipArm is None:
                    problem = ("'New tip each cell' needs PlateArm._draw in plate_robot.py, and the "
                               "deployed one doesn't have it. Use 'Same tip, whole run' for now.")
                else:
                    missing = plate_robot.location_problems(mode, cells)
                    if missing:
                        problem = "Fill these in plate_locations.py:\n" + "\n".join(missing[:10]) + \
                            ("\n(+{} more)".format(len(missing) - 10) if len(missing) > 10 else "")
            if problem:
                messagebox.showerror("Error", problem, parent=win)
                return
            arm = None
            if mode != "none":
                tip_text = ""
                if mode == "draw":
                    need = _tips_needed(tip_mode, len(cells))
                    try:
                        first = int(getattr(plate_robot.get_robot(), "pip_id", 0) or 0)
                    except (TypeError, ValueError):
                        first = 0
                    left = TIP_RACK_SIZE - first
                    tip_text = "\n{}: {} tip(s), rack index {} -> {}.".format(
                        tip_labels[tip_mode], need, first, first + need - 1)
                    if need > left:
                        tip_text += ("\n\nWARNING: only {} tip(s) left before pip_id wraps back to 0. "
                                     "Refill the rack and reset rob.pip_id first.".format(left))
                text = ("Draw {:g} mL from the source vial into each of {} cell(s).{}"
                        "\n\nSource vial uncapped and deck clear?".format(volume, len(cells), tip_text)
                        if mode == "draw" else
                        "Simulate on {} cell(s): 1 mL of air at the source vial approach, then each "
                        "cell's approach. Nothing is drawn.\n\nDeck clear?".format(len(cells)))
                if not messagebox.askokcancel("Arm will move", text, parent=win):
                    return
                try:
                    arm = _make_arm(plate_robot.get_robot(), mode, volume, tip_mode)
                except Exception as e:
                    messagebox.showerror("Error", "Could not set up the arm: {}".format(e), parent=win)
                    return
                arm.on_fault = lambda msg: self._ui(lambda: messagebox.showerror(
                    "Arm fault", "The arm stopped while filling {}\n\nNo more fills this run; tests "
                    "already running finish. Check the arm before moving it.".format(msg)))
            # remembered for next time (also in Settings -> MUX_CYCLE / CA)
            self.plate.config["mux_cycle_params"] = {"tests": tests, "liquid_mode": mode,
                                                     "volume_ml": volume, "ca_back_s": back,
                                                     "ca_end_s": end, "full": bool(full_var.get()),
                                                     "tip_mode": tip_mode}
            ca = dict(self.plate.config.get("ca_params") or {})
            ca["time_run"] = hold
            self.plate.config["ca_params"] = ca
            win.destroy()
            self._start_mux_cycle(cells, tests, arm, full=bool(full_var.get()))

        tk.Button(frame, text="Start", command=start, bg="#4CAF50", fg="white").grid(
            row=8, column=0, columnspan=2, pady=8)
        win.grab_set()

    def _start_mux_cycle(self, cells, tests, arm=None, full=False):
        """Plain Mux Cycle: one job queue + worker per mux, jobs in channel order
        carrying arm.fill. Lanes start MUX_LANE_GAP_S apart in mux order; a
        coordinator waits for all of them, then lets the arm drop its tip / park.
        Stop Run works as for Run All (the current test finishes)."""
        if full:
            return self._start_full(cells, tests, arm)
        self.log_notes_to_plate_log(auto=True)  # ran cells get their rows when they start
        sof = self.stop_on_fail.get()
        lanes = {}
        for c in sorted(cells):
            i, j = c // 4, c % 4
            cell = self.cells[i][j]
            cell.state = "queued"
            cell.stop_event = threading.Event()
            cell.history = []
            self._set_cell_ui(i, j, "queued")
            lanes.setdefault(c // 8, queue.Queue()).put(
                (i, j, tests, self.gen, sof, arm.fill if arm is not None else None))
        go = threading.Event()

        def lane(name, q, delay):
            go.wait()          # every thread of the run exists before any mux touches a
            time.sleep(delay)  # pstat (creating a thread mid-test crashed PEIS)
            self._worker(name, q)

        workers = []
        for k, (mi, q) in enumerate(lanes.items()):
            q.put(None)  # the lane exits after its mux's last cell
            workers.append(threading.Thread(target=lane, args=("mux{}".format(mi), q, k * MUX_LANE_GAP_S),
                                            daemon=True, name="mux_cycle_mux{}".format(mi)))

        def coordinator():
            for t in workers:
                t.join()
            note = ""
            if arm is not None:
                try:
                    note = arm.finish()
                except Exception as e:
                    note = "end-of-run arm move failed: {!r}".format(e)
                    traceback.print_exc()
            self._ui(lambda note=note: self.status_var.set(
                "Mux cycle finished" + (" - " + note if note else "")))

        self.mux_threads = [threading.Thread(target=coordinator, daemon=True, name="mux_cycle")]
        for t in workers + self.mux_threads:
            t.start()
        go.set()
        self.status_var.set("Mux cycle: {} cells on mux {}".format(len(cells), sorted(lanes)))

    def _start_full(self, cells, tests, arm=None):
        """FULL Mux Cycle: one triplet.run_full_mux lane per mux. Each cell has its
        own stop event (its STOP stops only that cell); each mux has one too
        (Stop Run sets those)."""
        try:
            groups, params, devices = triplet.prepare_full_run(self.plate, cells, tests=tests)
        except Exception as exc:
            messagebox.showerror("FULL", str(exc))
            return
        self.log_notes_to_plate_log(auto=True)
        go = threading.Event()
        events = {mi: threading.Event() for mi in groups}
        self.full_events = events
        cell_events = {}
        for mi, positions in groups.items():
            for row, col, hw in positions:
                i, j = row - 1, COL_LETTERS.index(col)
                cell = self.cells[i][j]
                cell.state, cell.history, cell.stop_event = "queued", [], threading.Event()
                cell_events[hw] = cell.stop_event
                cell.lane = mi
                self._set_cell_ui(i, j, "queued")
        outcomes = {}

        def lane(mi, positions, delay):
            go.wait()
            event = events[mi]
            ident = threading.get_ident()
            active_records = {}

            def notify(row, col, test, state, measurement, note):
                i, j = row - 1, COL_LETTERS.index(col)
                cell = self.cells[i][j]
                if test == "CA_SAVED":
                    # the cell's CA file is final (initial hold + CA back + CA end)
                    cell.kind = "CA"
                    cell.final_df = measurement.data
                    graph_note = self._full_graph(measurement, "CA")
                    for rec in cell.history:
                        if rec["test"] == "CA":
                            rec["df"] = measurement.data
                            if graph_note:
                                rec["note"] = (rec.get("note") or "") + ("; " if rec.get("note") else "") + graph_note
                    return
                if test == "CELL":  # this cell alone stopped; its mux keeps going
                    cell.state = "stopped"
                    self._ui(lambda i=i, j=j: self._set_cell_ui(i, j, "stopped"))
                    self._ui(lambda row=row, col=col: self.status_var.set(
                        f"FULL mux{mi}: {row}{col} stopped (rest of mux continues)"))
                    return
                key = (row, col, test)
                if state == "running":
                    cell.state = "running"
                    rec = {"test": test, "status": state, "note": note}
                    cell.history.append(rec)
                    active_records[key] = rec
                    cell.begin_test("CA" if test in ("CA_REVISIT", "CA_END") else test)
                    if test in ("PEIS", "CV"):
                        LIVE_ROUTES[ident] = cell
                    else:
                        LIVE_ROUTES.pop(ident, None)
                    self._ui(lambda i=i, j=j: self._set_cell_ui(i, j, "running"))
                    self._ui(lambda cid=f"{row}{col}": self.log_notes_to_plate_log(auto=True, ensure_cells=[cid]))
                else:
                    rec = active_records.pop(key, None)
                    if rec is not None:
                        rec.update(status=state, note=note)
                        if measurement is not None:
                            rec["df"] = measurement.data
                            cell.final_df = measurement.data
                            if test in ("PEIS", "CV") and state == "complete":
                                rec["note"] = self._full_graph(measurement, test) or rec["note"]
                    LIVE_ROUTES.pop(ident, None)
                self._ui(lambda row=row, col=col, test=test, state=state: self.status_var.set(
                    f"FULL mux{mi}: {row}{col} {test} {state}"))

            def sample(row, col, elapsed, current):
                self.cells[row - 1][COL_LETTERS.index(col)].push(elapsed, current)

            error = None
            try:
                if not event.wait(delay):
                    triplet.run_full_mux(self.plate, mi, positions, params, devices,
                                         stop_event=event, fill=arm.fill if arm is not None else None,
                                         notify=notify, sample_hook=sample,
                                         cell_events=cell_events)
            except Exception as exc:
                error = str(exc)
                traceback.print_exc()
            finally:
                LIVE_ROUTES.pop(ident, None)
                state = "failed" if error else "stopped" if event.is_set() else "done"
                outcomes[mi] = error or state
                for rec in active_records.values():
                    rec.update(status="failed" if error else "stopped", note=error or "stopped")
                for row, col, _ in positions:
                    i, j = row - 1, COL_LETTERS.index(col)
                    cell = self.cells[i][j]
                    if not error and not event.is_set() and cell.stop_event.is_set():
                        cell.state = "failed" if any(r.get("status") == "failed" for r in cell.history) else "stopped"
                    else:
                        cell.state = state if cell.history or error else "stopped"
                    cell.lane = None
                    self._ui(lambda i=i, j=j, s=cell.state: self._set_cell_ui(i, j, s))

        workers = [threading.Thread(target=lane, args=(mi, positions, k * MUX_LANE_GAP_S),
                                    daemon=True, name=f"full_mux{mi}")
                   for k, (mi, positions) in enumerate(groups.items())]

        def coordinator():
            for worker in workers:
                worker.join()
            note = ""
            if arm is not None:
                try:
                    note = arm.finish() or ""
                except Exception as exc:
                    note = str(exc)
            result = "; ".join(f"mux{mi}: {outcomes.get(mi, 'stopped')}" for mi in groups)
            self._ui(lambda: self.status_var.set("FULL finished - " + result + (" - " + note if note else "")))

        coordinator_thread = threading.Thread(target=coordinator, daemon=True, name="full_coordinator")
        self.mux_threads = workers + [coordinator_thread]
        for thread in self.mux_threads:
            thread.start()
        go.set()
        self.status_var.set(f"FULL: {len(cells)} cells on independent muxes {list(groups)}")

    # ---- settings ----

    def _apply_graphs(self):
        """Push the graph toggle into dataanalysis + plate config (Debug-tab
        checkbox, and once at startup before status_var exists). Sets both flag
        names so an older dataanalysis.py still obeys."""
        g = bool(self.graphs_var.get())
        self.plate.config["generate_graphs"] = g
        if dataanalysis is not None:
            dataanalysis.GRAPHS_ENABLED = g
            dataanalysis.CAPACITANCE_GRAPHS = g
        if hasattr(self, "status_var"):
            self.status_var.set("Graph generation {}".format("ON" if g else "OFF"))

    def open_settings(self):
        defaults = triplet.PARAM_DEFAULTS
        win = tk.Toplevel(self.root)
        win.title("Settings - " + self.plate.plate_id)
        nb = ttk.Notebook(win)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._settings_entries = {}
        # every registered test gets a tab (CA_CYCLE has its own dialog)
        for test in [t for t in defaults if t != "CA_CYCLE"]:
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

        # Debug tab: its checkboxes apply the moment they are clicked, and save()
        # only walks _settings_entries, so this tab is invisible to it
        dbg = tk.Frame(nb, padx=8, pady=8)
        nb.add(dbg, text="Debug")
        tk.Checkbutton(dbg, text="Stop series on failure",
                       variable=self.stop_on_fail).grid(row=0, column=0, sticky="w", pady=3)
        tk.Checkbutton(dbg, text="Generate graphs (PNGs after each test)",
                       variable=self.graphs_var,
                       command=self._apply_graphs).grid(row=1, column=0, sticky="w", pady=3)
        tk.Button(dbg, text="Upsert Mongo", command=self.upsert_mongo).grid(
            row=2, column=0, sticky="w", pady=3)

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
        fn = triplet.backfill_plate_data
        self.status_var.set("Mongo upsert running ...")

        def job():  # own thread: file reads + network only, never toolkitpy
            try:
                fn(".")
                self._ui(lambda: self.status_var.set(
                    "Mongo upsert done (includes plate {})".format(self.plate.plate_id)))
            except Exception as e:
                self._ui(lambda e=e: self.status_var.set("Mongo upsert failed: {!r}".format(e)))
                traceback.print_exc()
        threading.Thread(target=job, daemon=True).start()


FullPlateGrid = PlateGrid  # old name, kept for anything that still imports it


def new_plate():
    """Use instead of Plate(...); the GUI creates the Plate object."""
    holder = {}
    root = tk.Tk()
    PlateSetup(root, holder)
    try:
        root.mainloop()
    finally:  # Ctrl+C / Interrupt lands here: stop the runs and release first
        grid = holder.get("grid")
        if grid is not None:
            grid.shutdown_blocking()
    return holder.get("plate")


if __name__ == "__main__":
    new_plate()