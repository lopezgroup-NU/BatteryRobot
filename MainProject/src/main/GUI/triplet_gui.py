#NOTE: include individual machine status lights

import ast
import inspect
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

try:
    from utils.PStat import triplet  # same module object BatteryRobotUtils star-imports
except ImportError:
    import triplet  # fallback when run directly from utils/PStat

# FIX: graph toggle -- the Debug-tab checkbox flips dataanalysis.CAPACITANCE_GRAPHS
try:
    from utils.PStat import dataanalysis
except ImportError:
    try:
        import dataanalysis
    except ImportError:
        dataanalysis = None

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
COL_LETTERS = ["A", "B", "C", "D"]  # plate columns run A-D left->right (no Excel mirror)
N_MUX = 3

# RELEASE_SHELL=True frees the IDE shell after Create Plate (root.quit()).
# The Gamry access violations only ever occurred in that mode -- the COM layer
# seems to rely on the real Tk mainloop pumping messages on the main thread --
# ideally it stays False.
RELEASE_SHELL = False

# Number of hardware worker threads. 1 = tests run one cell at a time in a
# single dedicated thread (matches the intended workflow and keeps the Gamry
# layer on one thread). Raising it restores parallel per-mux testing but is
# NOT stable with the current toolkitpy behavior.
HARDWARE_WORKERS = 1

# Established status colors
C_IDLE = None            # filled with the platform default button bg at startup
C_BUSY = "#FFF59D"       # queued / running
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

TEST_ALIASES = {"CAP": "CAPACITANCE"}

def _canon_test(name):
    t = str(name).strip().upper()
    fn = getattr(triplet, "conon_test", None)
    if fn is not None:
        try:
            return fn(t)
        except Exception:
            pass
    return TEST_ALIASES.get(t, t)

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
    "CAPACITANCE": ("Vf (V)", "Im (A)"),   # live overlay of the per-rate CV loops
}
FINAL_COLS = {
    "PEIS": (["zreal", "z_real"], ["zimag", "z_imag"]),
    "CV": (["vf", "voltage"], ["im", "current"]),
    "CA": (["time", "t"], ["im", "current"]),
    "CAPACITANCE": (["vf", "voltage"], ["im", "current"]),   # overlay of all rates
}


def _peis_intercept(xs, ys):
    """Zreal at the smallest non-negative -Zimag (same math as eis_interpret)."""
    best_x = best_y = None
    for x, y in zip(xs, ys):
        if y >= 0 and (best_y is None or y < best_y):
            best_x, best_y = x, y
    return best_x


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
    - queue mode (CA cycle): drains a route queue, finish(df) draws final data.
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
            # no plottable x/y in the final output (e.g. Capacitance summary
            # table) -- keep the live trace on screen
            if self.xs:
                self._redraw(force_scale=True)
            self.status.set("complete - {} live pts kept (final output has no plottable columns)".format(
                len(self.xs)))


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
        fields = [("Plate ID", ""), ("Operator", ""), ("Hypothesis", ""), ("Notes", ""),
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
        # read every entry BEFORE the setup widgets are destroyed below
        pid = self.vars["Plate ID"].get().strip()
        tests_string = self.vars["Tests (order)"].get()
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
                params = inspect.signature(rs).parameters
                if "hypothesis" in params:
                    kwargs["hypothesis"] = config["hypothesis"]
                if "operator" in params:
                    kwargs["operator"] = config["operator"]
                rs(plate.plate_id, plate.created_at, **kwargs)
            except Exception as e:
                print("sample log auto-record failed: {!r}".format(e))
        # reuse the same Tk root for the grid (a second Tk() instance leaves
        # tkinter without a valid default root, which confuses the IDE's pump)
        for child in list(self.root.winfo_children()):
            child.destroy()
        PlateGrid(self.root, plate, tests_string, self.holder)
        if RELEASE_SHELL:
            self.root.quit()


class PlateGrid:
    """6x4 cell grid: per-cell RUN/STOP + STATUS + VIEW, one worker per MUX
    (3 concurrent runs max), stop-on-fail toggle, tabbed test settings,
    on-demand live graphs."""

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
        # FIX: checkbutton moved to Settings -> Debug; the var stays here
        # because run_cell/run_all snapshot it on the UI thread
        self.stop_on_fail = tk.BooleanVar(master=root, value=True)
        # FIX: graph toggle. Same pattern as stop_on_fail: var lives here,
        # checkbox lives in Settings -> Debug and applies instantly (the Debug
        # tab is invisible to save()). Remembered in plate config.
        self.graphs_var = tk.BooleanVar(
            master=root,
            value=bool(self.plate.config.get(
                "generate_graphs",
                (getattr(dataanalysis, "GRAPHS_ENABLED",
                         getattr(dataanalysis, "CAPACITANCE_GRAPHS", True))
                 if dataanalysis else True))))
        self._apply_graphs()  # push a saved/previous choice into dataanalysis now

        self.grid_frame = tk.Frame(self.main_frame)
        self.grid_frame.pack(pady=10)
        self.cells = []        # CellState grid
        self.entries = []      # FIX: per-cell contents/notes entries are back
        self.run_buttons = []  # FIX: doubles as the status light (no STATUS button)
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
                # right-click the RUN button for the per-test status popup
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
        self.gen = 0  # bumped by Stop Run; stale-generation jobs are skipped
        self.jobs = queue.Queue()  # single queue: cells run one at a time
        for w in range(HARDWARE_WORKERS):
            threading.Thread(target=self._worker, args=(w,), daemon=True).start()
        self._poll_ui()

        button_frame = tk.Frame(self.main_frame)
        button_frame.pack(pady=10)
        # FIX: bottom bar is Clear Status / CA Cycle / Log Notes / New Plate;
        # Upsert Mongo lives in Settings -> Debug. The separate cell-notes CSV
        # (Save/Load CSV + path field) is REMOVED -- the plate log is the one
        # and only persistence for cell notes now.
        tk.Button(button_frame, text="Clear Status", command=self.clear_statuses).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="CA Cycle", command=self.ca_cycle).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Log Notes",
                  command=self.log_notes_to_plate_log).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="New Plate", command=self.new_plate_button).pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(master=root)
        self.status_var.set("Ready")
        tk.Label(self.main_frame, textvariable=self.status_var, bd=1,
                 relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    # ---- per-cell button handlers ----

    def toggle_cell(self, i, j):
        cell = self.cells[i][j]
        if cell.state in ("queued", "running"):
            cell.stop_event.set()
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
        colors = {"running": C_BUSY, "queued": C_BUSY, "complete": C_DONE,
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
        """UI-thread only: color + text on the merged RUN/status button."""
        colors = {"idle": C_IDLE, "queued": C_BUSY, "running": C_BUSY,
                  "done": C_DONE, "failed": C_FAIL, "stopped": C_IDLE}
        btn = self.run_buttons[i][j]  # FIX: status light lives on RUN now
        btn.config(bg=colors.get(state, C_IDLE))
        if state in ("queued", "running"):
            btn.config(text="STOP", state=tk.NORMAL)
        else:
            btn.config(text="RUN", state=tk.NORMAL)

    # ---- running tests ----

    def parse_tests(self):
        raw = self.tests_entry.get().replace(",", " ").split()
        tests = [_canon_test(t) for t in raw if t.strip()]   # FIX: "CAP" -> "CAPACITANCE"
        valid = list(getattr(triplet, "TEST_RUNNERS", {})) or list(getattr(triplet, "test_types", ("PEIS", "CV", "CA")))
        unknown = [t for t in tests if t not in valid]
        if not tests or unknown:
            messagebox.showerror("Error", "Unknown/empty tests: {}. Available: {} "
                                 "(aliases: CAP=CAPACITANCE)".format(unknown, valid))
            return None
        return tests

    def run_cell(self, i, j):
        tests = self.parse_tests()
        if tests is None:
            return
        # FIX: notes-only here (any noted cell may be logged); the ran-cell
        # row is ensured by the worker when the cell ACTUALLY starts running,
        # so a Stop Run while still queued never logs a cell that never ran
        self.log_notes_to_plate_log(auto=True)
        cell = self.cells[i][j]
        cell.state = "queued"
        cell.stop_event = threading.Event()
        cell.history = []
        self._set_cell_ui(i, j, "queued")
        self.status_var.set("Queued: {}{}".format(i + 1, COL_LETTERS[j]))
        # snapshot the toggle on the UI thread; workers must not touch tk vars
        self.jobs.put((i, j, tests, self.gen, self.stop_on_fail.get()))

    def run_all(self):
        tests = self.parse_tests()
        if tests is None:
            return
        # FIX: notes-only here (any noted cell may be logged); each ran cell's
        # row is ensured by the worker when that cell ACTUALLY starts running,
        # so cells stopped while still queued never get logged
        self.log_notes_to_plate_log(auto=True)
        sof = self.stop_on_fail.get()
        for i in range(ROWS):
            for j in range(COLS):
                cell = self.cells[i][j]
                if cell.state in ("queued", "running"):
                    continue
                cell.state = "queued"
                cell.stop_event = threading.Event()
                cell.history = []
                self._set_cell_ui(i, j, "queued")
                self.jobs.put((i, j, tests, self.gen, sof))
        self.status_var.set("Queued all cells (run one at a time)")

    def stop_run(self):
        self.gen += 1  # invalidates queued jobs
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
        """FIX: tear this grid down and reopen the New Plate dialog on the
        same Tk root -- identical flow to new_plate(), minus the new Tk()."""
        busy = any(cell.state in ("queued", "running")
                   for row in self.cells for cell in row)
        if busy or any(t.is_alive() for t in getattr(self, "ca_cycle_threads", [])):
            messagebox.showerror("Error", "Tests are running - Stop Run first")
            return
        self._closed = True                  # stops _poll_ui rescheduling
        for _ in range(HARDWARE_WORKERS):    # unblock workers so they exit
            self.jobs.put(None)
        for child in list(self.root.winfo_children()):
            child.destroy()                  # also closes any LiveView popups
        PlateSetup(self.root, self.holder)

    # ---- plate log (cell notes) ----
    # FIX: the old cell-notes CSV (Save/Load CSV + _csv_target) is removed;
    # the plate log below is the single home for cell notes.

    def log_notes_to_plate_log(self, auto=False, ensure_cells=None):
        """FIX: upsert this plate's cell-entry notes into the plate log CSV
        (triplet.PLATE_LOG_DIRECTORY). One row per cell keyed on
        (PlateID, Cell Position e.g. 3A); the note lands in a 'Cell Notes'
        column kept as the LAST column, to the right of 'Comments'.
        ensure_cells: cell ids that must have a row even with a BLANK note --
        the worker passes each cell the moment it actually starts running
        (and CA Cycle passes its selected cells at launch), so ONLY cells
        that really run tests, or cells with notes, ever appear in the log.
        Non-empty entries overwrite that cell's previous note; blank entries
        never blank out an existing note; Material/Comments columns are never
        touched; nothing is rewritten when there is no actual change.
        auto=True (run starts) is silent when there is nothing to do and never
        pops a modal dialog -- a log problem must not block hardware."""
        import os
        import pandas as pd
        path = getattr(triplet, "PLATE_LOG_DIRECTORY", None)
        if not path:
            self.status_var.set("PLATE_LOG_DIRECTORY not found in triplet.py")
            return
        cols = list(getattr(triplet, "PLATE_LOG_COLS",
                            ["PlateID", "Cell Position", "Material Name",
                             "Catalyst Loading", "Nafion Loading",
                             "Carbon Black Loading", "Extracted Data", "Comments"]))
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
            for cell_id in sorted(want):
                mask = (df["PlateID"] == pid) & (df["Cell Position"] == cell_id)
                if mask.any():
                    # existing row: only touch Cell Notes when there IS a note,
                    # and only when it actually changed
                    if cell_id in notes and \
                            (df.loc[mask, "Cell Notes"] != notes[cell_id]).any():
                        df.loc[mask, "Cell Notes"] = notes[cell_id]
                        updated += int(mask.sum())
                else:
                    row = {c: "" for c in df.columns}
                    row["PlateID"] = pid
                    row["Cell Position"] = cell_id
                    row["Cell Notes"] = notes.get(cell_id, "")
                    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                    added += 1
            if added or updated:      # FIX: no pointless rewrite every run start
                df.to_csv(path, index=False)
        except Exception as e:
            # FIX: Exception, not just OSError -- a mangled CSV must not crash
            # a run start. Manual press gets the dialog; auto stays non-modal.
            if auto:
                print("[gui] plate log auto-update failed: {!r}".format(e))
                self.status_var.set("Plate log auto-update failed (run continues)")
            else:
                messagebox.showerror("Error", "Could not write the plate log ({}) -- "
                                     "is it open in Excel?\n{}".format(path, e))
            return
        if added or updated or not auto:
            self.status_var.set("Plate log: {} row(s) added, {} updated -> {}".format(
                added, updated, path))

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
        if getattr(self, "_closed", False):  # FIX: grid replaced by New Plate
            return
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

    def _measure(self, row, col, t, stop_event):
        """Call triplet.measure, passing stop_event only if it accepts one."""
        kwargs = {}
        try:
            if "stop_event" in inspect.signature(triplet.measure).parameters:
                kwargs["stop_event"] = stop_event
        except (TypeError, ValueError):
            pass
        return triplet.measure(self.plate, row, col, t, **kwargs)

    def _measurement_base(self, meas, row, col, test):
        """FIX: resolve <cellfolder>/<stem>_<TEST> exactly the way
        write_measurement builds it. Prefers an explicit path attribute if
        the dataclass ever grows one; otherwise reconstructs from
        triplet.DATA_DIRECTORY + _stem. Returns (base, None) or
        (None, short_reason); details go to the shell."""
        import os
        for attr in ("path", "filepath", "file_path", "csv_path", "data_path",
                     "filename", "fname"):
            v = getattr(meas, attr, None)
            if v:
                base = str(v)
                if os.path.isdir(base):
                    return os.path.join(base, "{}{}_{}".format(row, col, test)), None
                return os.path.splitext(base)[0], None
        data_dir = getattr(triplet, "DATA_DIRECTORY", None)
        if not data_dir:
            print("[gui] test outputs skipped: triplet.DATA_DIRECTORY not found")
            return None, "no DATA_DIRECTORY (see shell)"
        cell_id = getattr(meas, "cell_id", None) or "{}{}".format(row, col)
        tname = getattr(meas, "electrochemical_test", None) or test
        stem_fn = getattr(triplet, "_stem", None)
        stem = stem_fn(self.plate.plate_id, cell_id) if stem_fn else \
            "{}_{}".format(self.plate.plate_id, cell_id)
        cell_dir = os.path.join(str(data_dir), stem)
        if not os.path.isdir(cell_dir):
            print("[gui] test outputs skipped: expected cell folder "
                  "not found: {}".format(cell_dir))
            return None, "cell folder not found (see shell)"
        return os.path.join(cell_dir, "{}_{}".format(stem, tname)), None

    def _cap_analysis_outputs(self, meas, df, row, col):
        """FIX: write the capacitance points CSV + PNGs into the cell folder
        next to the measurement. Returns a short outcome note (shown in the
        right-click status popup); details go to the shell. Never raises."""
        if dataanalysis is None:
            print("[gui] capacitance outputs skipped: dataanalysis import failed at GUI startup")
            return "graphs skipped: dataanalysis import failed"
        fn = getattr(dataanalysis, "save_capacitance_graphs_from_df", None)
        if fn is None:
            print("[gui] capacitance outputs skipped: the deployed dataanalysis.py is OLD -- "
                  "redeploy it (save_capacitance_graphs_from_df is missing)")
            return "graphs skipped: old dataanalysis.py deployed"
        base, err = self._measurement_base(meas, row, col, "CAPACITANCE")
        if base is None:
            return "graphs skipped: " + err
        import os
        try:
            p = triplet._resolve_params(self.plate, "CAPACITANCE", None)
        except Exception:
            p = dict(getattr(triplet, "PARAM_DEFAULTS", {}).get("CAPACITANCE", {}))
        tv = p.get("target_voltage")
        if tv is None and "v_low" in p and "v_high" in p:
            tv = (float(p["v_low"]) + float(p["v_high"])) / 2.0
        out = fn(df, base, target_voltage=tv)     # never raises; prints its own log
        folder = os.path.dirname(base) or os.getcwd()
        if out:
            return "graphs -> {}".format(folder)
        return "points csv -> {} (graphs off, <2 rates, or see shell)".format(folder)

    def _test_graph_output(self, meas, df, row, col, t):
        """FIX: save the final-data PNG for a completed PEIS/CV/CA test into
        the cell folder next to the measurement CSVs. Returns a short outcome
        note for the right-click status popup; never raises."""
        if dataanalysis is None:
            return "graph skipped: dataanalysis import failed"
        fn = getattr(dataanalysis, "save_test_graph", None)
        if fn is None:
            print("[gui] test graph skipped: the deployed dataanalysis.py is OLD -- "
                  "redeploy it (save_test_graph is missing)")
            return "graph skipped: old dataanalysis.py deployed"
        base, err = self._measurement_base(meas, row, col, t)
        if base is None:
            return "graph skipped: " + err
        import os
        p = fn(df, t, base)                        # never raises; prints its own log
        if p:
            return "graph -> {}".format(os.path.dirname(p))
        return "no graph (off or see shell)"

    def _worker(self, worker_id):
        while True:
            job = self.jobs.get()
            if job is None:  # FIX: shutdown sentinel from New Plate
                return
            i, j, tests, gen, stop_on_fail = job
            cell = self.cells[i][j]
            if gen != self.gen or cell.stop_event.is_set():
                cell.state = "stopped" if cell.stop_event.is_set() else "idle"
                self._ui(lambda i=i, j=j, s=cell.state: self._set_cell_ui(i, j, s))
                continue
            row, col = i + 1, COL_LETTERS[j]
            cell.state = "running"
            self._ui(lambda i=i, j=j: self._set_cell_ui(i, j, "running"))
            # FIX: only cells that ACTUALLY start running get a plate-log row.
            # Routed through ui_q because the logger reads tk entry widgets
            # (workers must never touch tkinter directly).
            self._ui(lambda cid="{}{}".format(row, col): self.log_notes_to_plate_log(
                auto=True, ensure_cells=[cid]))
            failed = []
            stopped = False
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
                    meas = self._measure(row, col, t, cell.stop_event)
                    df = getattr(meas, "data", None) if meas is not None else None
                    if cell.stop_event.is_set():
                        rec["status"] = "stopped"
                        stopped = True
                    elif df is None:
                        rec["status"] = "failed"  # when measure() caught an internal failure
                        failed.append(t)
                    else:
                        rec["status"] = "complete"
                        # FIX: per-test outputs go into the cell folder;
                        # CAPACITANCE gets its pair + points CSV, every other
                        # test gets one final-data PNG. Outcome lands in
                        # rec["note"] (right-click status popup).
                        try:
                            if t == "CAPACITANCE":
                                rec["note"] = self._cap_analysis_outputs(meas, df, row, col)
                            else:
                                rec["note"] = self._test_graph_output(meas, df, row, col, t)
                        except Exception:
                            import traceback
                            traceback.print_exc()
                except Exception as e:
                    rec["status"] = "failed"
                    rec["note"] = repr(e)[:120]
                    failed.append(t)
                    import traceback
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

    # ---- CA cycle (kept as its own separate flow) ----

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
            # FIX: every ran cell gets a plate-log row, note or not
            self.log_notes_to_plate_log(
                auto=True, ensure_cells=["{}{}".format(c // 4 + 1, COL_LETTERS[c % 4])
                                         for c in cells])

            by_mux = {}
            for c in cells:
                by_mux.setdefault(c // 8, []).append(c)
            self.ca_cycle_stop = threading.Event()
            self.ca_cycle_threads = []
            for c in cells:
                i, j = c // 4, c % 4
                self.cells[i][j].history.append({"test": "CA_CYCLE", "status": "running", "note": ""})
                self.run_buttons[i][j].config(bg=C_BUSY)  # FIX: merged status light
            self.status_var.set("CA cycle: {} cells on mux {}".format(len(cells), sorted(by_mux)))
            done = {"n": 0, "total": len(by_mux)}

            def worker(mi, cs):
                ident = threading.get_ident()
                route = queue.Queue()
                LIVE_ROUTES[ident] = QueueTarget(route)
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
                    try:  # combined final trace for the popup
                        import pandas as pd
                        frames = [m.data for m in ms if getattr(m, "data", None) is not None and len(m.data)]
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
                self._ui(lambda h=holder, df=df, ok=ok: h.get("p") and h["p"].finish(df, failed=not ok))

                def fin(msg=msg, ok=ok, cs=cs):
                    bg = C_DONE if ok else C_FAIL
                    status = "complete" if ok else "failed"
                    for c in cs:
                        i, j = c // 4, c % 4
                        self.run_buttons[i][j].config(bg=bg)  # FIX: merged status light
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

    # ---- settings ----

    def _apply_graphs(self):
        """FIX: push the graph toggle into dataanalysis + plate config.
        Called by the Debug-tab checkbox (default ON) and once at startup;
        hasattr guard because status_var does not exist yet at startup.
        Sets BOTH flag names so an older deployed dataanalysis.py still obeys."""
        g = bool(self.graphs_var.get())
        self.plate.config["generate_graphs"] = g
        if dataanalysis is not None:
            dataanalysis.GRAPHS_ENABLED = g        # all-test master switch
            dataanalysis.CAPACITANCE_GRAPHS = g    # back-compat name
        if hasattr(self, "status_var"):
            self.status_var.set("Graph generation {}".format("ON" if g else "OFF"))

    def open_settings(self):
        # NOTE: change time to minutes from seconds
        defaults = getattr(triplet, "PARAM_DEFAULTS", None)
        if not defaults:
            self.status_var.set("PARAM_DEFAULTS not found in triplet.py")
            return
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

        # FIX: Debug tab -- run-control toggle + maintenance actions moved off
        # the main page. save() only walks _settings_entries, so this tab is
        # invisible to it.
        dbg = tk.Frame(nb, padx=8, pady=8)
        nb.add(dbg, text="Debug")
        tk.Checkbutton(dbg, text="Stop series on failure",
                       variable=self.stop_on_fail).grid(row=0, column=0, sticky="w", pady=3)
        # FIX: graph toggle -- applies the moment it is clicked (no Save
        # needed, matching stop_on_fail) and is remembered in plate config
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
        fn = getattr(triplet, "backfill_plate_data", None)
        if fn is None:
            self.status_var.set("backfill_plate_data not found in triplet.py")
            return
        self.status_var.set("Mongo upsert running ...")

        def job():  # own thread: file reads + network only, never toolkitpy
            try:
                fn(".")
                self._ui(lambda: self.status_var.set(
                    "Mongo upsert done (includes plate {})".format(self.plate.plate_id)))
            except Exception as e:
                self._ui(lambda e=e: self.status_var.set("Mongo upsert failed: {!r}".format(e)))
                import traceback
                traceback.print_exc()
        threading.Thread(target=job, daemon=True).start()


def new_plate():
    """Use instead of Plate(...); the GUI will create the Plate object"""
    holder = {}
    root = tk.Tk()
    PlateSetup(root, holder)
    root.mainloop()
    return holder.get("plate")


if __name__ == "__main__":
    new_plate()


# NOTE: dev menu, somewhere else  (Debug tab in Settings covers this for now?)