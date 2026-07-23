import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import queue
import threading

try:
    from utils.PStat import triplet  # same module object BatteryRobotUtils star-imports
except ImportError:
    import triplet  # fallback when run directly from utils/PStat

ROWS = 6
COLS = 4
COL_LETTERS = ["A", "B", "C", "D"]  # plate columns run A-D left->right (no Excel mirror)


def _valid_tests():
    runners = getattr(triplet, "TEST_RUNNERS", None)
    if runners:
        return list(runners)
    return list(getattr(triplet, "test_types", ("PEIS", "CV", "CA")))


class PlateSetup:
    """First window: creates the Plate, then opens the grid."""

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

        grid_window = tk.Tk()
        PlateGrid(grid_window, plate, self.vars["Tests (order)"].get(), self.holder)
        self.root.destroy()


class PlateGrid:
    """6x4 cell grid: per-cell label + Run button, editable test order, CSV save/load."""

    def __init__(self, root, plate, tests_string, holder, filename="config/plate_layout.csv"):
        self.root = root
        self.plate = plate
        self.holder = holder
        self.filename = filename
        self.rows = ROWS
        self.cols = COLS
        self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]

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
        self.jobs = queue.Queue()
        self.ui_q = queue.Queue()
        self.gen = 0  # bumped by Stop Run; stale-generation jobs are skipped
        self.ca_stop = None  # threading.Event while an overnight CA is live
        threading.Thread(target=self._worker, daemon=True).start()
        self._poll_ui()

        button_frame = tk.Frame(self.main_frame)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Load CSV", command=self.load_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Save CSV", command=self.save_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Log Sample", command=self.log_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="CA Settings", command=self.overnight_ca).pack(side=tk.LEFT, padx=5)

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
        valid = _valid_tests()
        unknown = [t for t in tests if t not in valid]
        if not tests or unknown:
            messagebox.showerror("Error", "Unknown/empty tests: {}. Available: {}".format(unknown, valid))
            return None
        return tests

    def run_cell(self, i, j):
        tests = self.parse_tests()
        if tests is None:
            return
        self.run_buttons[i][j].config(bg="#FFF59D")
        self.status_var.set("Queued: {}{}".format(i + 1, COL_LETTERS[j]))
        self.jobs.put((i, j, tests, self.gen))

    def run_all(self):
        tests = self.parse_tests()
        if tests is None:
            return
        for i in range(self.rows):
            for j in range(self.cols):
                self.run_buttons[i][j].config(bg="#FFF59D")
                self.jobs.put((i, j, tests, self.gen))
        self.status_var.set("Queued all 24 cells")

    def stop_run(self):
        self.gen += 1  # invalidates the running cell's remaining tests
        if self.ca_stop is not None:
            self.ca_stop.set()  # also ends a live overnight CA early
        try:
            while True:
                i, j, _, _ = self.jobs.get_nowait()
                self.run_buttons[i][j].config(bg=self.default_btn_bg)
        except queue.Empty:
            pass
        self.status_var.set("Stopping after current test ...")

    def _ui(self, fn):
        self.ui_q.put(fn)  # worker thread must never touch tkinter directly

    def _poll_ui(self):
        try:
            while True:
                self.ui_q.get_nowait()()
        except queue.Empty:
            pass
        self.root.after(100, self._poll_ui)

    def _worker(self):
        while True:
            i, j, tests, gen = self.jobs.get()
            if gen != self.gen:
                self._ui(lambda i=i, j=j: self.run_buttons[i][j].config(bg=self.default_btn_bg))
                continue
            row, col = i + 1, COL_LETTERS[j]
            btn = self.run_buttons[i][j]
            failed = []
            stopped = False
            for t in tests:
                if gen != self.gen:
                    stopped = True
                    break
                self._ui(lambda t=t, row=row, col=col: self.status_var.set("Running {} on {}{} ...".format(t, row, col)))
                try:
                    m = triplet.measure(self.plate, row, col, t)
                    if m is not None and getattr(m, "data", True) is None:
                        failed.append(t)  # measure() caught a runner failure internally
                except Exception:
                    failed.append(t)
                    import traceback
                    traceback.print_exc()
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

    def overnight_ca(self):
        """Simultaneous CA on one cell per mux via triplet.run_overnight_ca.
        Runs on its own thread (not the cell queue) -- do NOT queue grid cells
        while it is live; both would fight over the same IFCs."""
        win = tk.Toplevel(self.root)
        win.title("CA Settings")
        frame = tk.Frame(win, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)
        fields = [("Cells", "0,8"), ("Voltage (V)", "1.65"),
                  ("Hours", "4"), ("Sample period (s)", "0.5")]
        entries = {}
        for i, (label, default) in enumerate(fields):
            tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=4)
            e = tk.Entry(frame, width=16)
            e.grid(row=i, column=1, padx=5, pady=4)
            e.insert(0, default)
            entries[label] = e

        def start():
            try:
                cells = tuple(int(t) for t in entries["Cells"].get().replace(",", " ").split())
                voltage = float(entries["Voltage (V)"].get())
                secs = int(float(entries["Hours"].get()) * 3600)
                sample = float(entries["Sample period (s)"].get())
            except ValueError:
                messagebox.showerror("Error", "Bad number in one of the fields")
                return
            if not cells or len(set(c // 8 for c in cells)) != len(cells):
                messagebox.showerror("Error", "One cell per mux only, e.g. 0,8,16")
                return
            win.destroy()
            self.ca_stop = threading.Event()
            self.status_var.set("CA running on cells {}".format(cells))

            def job():
                try:
                    triplet.run_overnight_ca(cells=cells, voltage=voltage, time_run=secs,
                                             sample_period=sample, stop_event=self.ca_stop)
                    self._ui(lambda: self.status_var.set("CA done: {}".format(cells)))
                except Exception as e:
                    self._ui(lambda e=e: self.status_var.set("CA failed: {!r}".format(e)))
                    import traceback
                    traceback.print_exc()
                finally:
                    self.ca_stop = None

            threading.Thread(target=job, daemon=True).start()

        tk.Button(frame, text="Start", command=start,
                  bg="#4CAF50", fg="white").grid(row=len(fields), column=0, columnspan=2, pady=8)
        win.grab_set()

    def log_sample(self):
        win = tk.Toplevel(self.root)
        win.title("Log Sample")
        frame = tk.Frame(win, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        prefill = [("Plate ID", self.plate.plate_id),
                   ("Date", self.plate.created_at.strftime("%Y%m%d")),
                   ("Notes", self.plate.config.get("notes", ""))]
        entries = {}
        for i, (label, default) in enumerate(prefill):
            tk.Label(frame, text=label).grid(row=i, column=0, sticky="e", padx=5, pady=4)
            e = tk.Entry(frame, width=32)
            e.grid(row=i, column=1, padx=5, pady=4)
            e.insert(0, default)
            entries[label] = e

        def save():
            pid = entries["Plate ID"].get().strip()
            notes = entries["Notes"].get().strip()
            self.plate.config["notes"] = notes  # keep config in sync with the log
            triplet.record_sample(pid, entries["Date"].get().strip(), notes)
            self.status_var.set("Sample log updated: " + pid)
            win.destroy()

        tk.Button(frame, text="Save to sample_log", command=save,
                  bg="#4CAF50", fg="white").grid(row=len(prefill), column=0, columnspan=2, pady=8)
        win.grab_set()

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
                self.run_buttons[i][j].config(bg=self.default_btn_bg)
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