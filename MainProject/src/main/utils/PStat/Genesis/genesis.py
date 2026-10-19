# genesis.py
# Genesis records and timed additions for multiple vials sharing one arm.
# Independent of triplet and the electrolyte database; Run links records by ID.

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from itertools import count
from typing import Callable, Optional
import heapq
import threading
import time

import pandas as pd

# ======= IDs =======

_ID_WIDTH = 3
_counters: dict[str, count] = {}

def new_id(prefix: str) -> str:
    """Return the next ID for a prefix, such as RUN-001."""
    if prefix not in _counters:
        _counters[prefix] = count(1)
    return f"{prefix}-{next(_counters[prefix]):0{_ID_WIDTH}d}"

RUN_STATUSES = ("queued", "running", "complete", "failed", "aborted")


# ======= Data Types =======

@dataclass
class Preparation:
    """A sample or cell preparation that runs can reference."""
    preparation_id: str = field(default_factory=lambda: new_id("PREP"))
    created_at: datetime = field(default_factory=datetime.now)
    operator_id: str = ""
    method: str = ""                                  # e.g. "dropcast", "ink"
    materials: dict = field(default_factory=dict)     # e.g. {"catalyst": ..., "loading_ug_cm2": ...}
    params: dict = field(default_factory=dict)
    notes: str = ""


@dataclass
class TestingProtocol:
    """A named test recipe with instrument parameters."""
    test_protocol_id: str = field(default_factory=lambda: new_id("TEST"))
    created_at: datetime = field(default_factory=datetime.now)
    name: str = ""
    technique: str = ""                               # "PEIS", "CV", "CA", "Capacitance", ...
    params: dict = field(default_factory=dict)        # resolved instrument parameters
    notes: str = ""


@dataclass
class Run:
    """One test run on a cell."""
    run_id: str = field(default_factory=lambda: new_id("RUN"))
    campaign_id: str = ""
    device_id: str = ""
    cell_id: str = ""
    test_protocol_id: str = ""
    preparation_id: str = ""                          # link to Preparation, if any
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    operator_id: str = ""
    run_status: str = "queued"
    data_path: str = ""                               # raw data location
    results: dict = field(default_factory=dict)       # extracted analysis values

    def __post_init__(self):
        if self.run_status not in RUN_STATUSES:
            raise ValueError(f"run_status must be one of {RUN_STATUSES}, got {self.run_status!r}")

    @property
    def duration_s(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    def mark(self, status: str) -> None:
        if status not in RUN_STATUSES:
            raise ValueError(f"run_status must be one of {RUN_STATUSES}, got {status!r}")
        self.run_status = status
        if status == "running" and self.start_time is None:
            self.start_time = datetime.now()
        if status in ("complete", "failed", "aborted"):
            self.end_time = datetime.now()


@dataclass
class LearningHistory:
    """A learning step with its source runs, inputs, and results."""
    learning_id: str = field(default_factory=lambda: new_id("LEARN"))
    created_at: datetime = field(default_factory=datetime.now)
    run_ids: list[str] = field(default_factory=list)
    inputs: dict = field(default_factory=dict)        # model inputs
    outputs: dict = field(default_factory=dict)       # suggestions and scores
    model: str = ""                                   # model name
    notes: str = ""


# ======= Registry =======

class GenesisDB:
    """Store records in memory by ID and export them to CSV."""

    def __init__(self):
        self.preparations: dict[str, Preparation] = {}
        self.protocols: dict[str, TestingProtocol] = {}
        self.runs: dict[str, Run] = {}
        self.learning: dict[str, LearningHistory] = {}

    def add(self, record):
        table, key = self._locate(record)
        table[getattr(record, key)] = record
        return record

    def _locate(self, record):
        if isinstance(record, Preparation):
            return self.preparations, "preparation_id"
        if isinstance(record, TestingProtocol):
            return self.protocols, "test_protocol_id"
        if isinstance(record, Run):
            return self.runs, "run_id"
        if isinstance(record, LearningHistory):
            return self.learning, "learning_id"
        raise TypeError(f"Unknown record type: {type(record).__name__}")

    def runs_for_campaign(self, campaign_id: str) -> list[Run]:
        return [r for r in self.runs.values() if r.campaign_id == campaign_id]

    def to_dataframe(self, table_name: str) -> pd.DataFrame:
        table = getattr(self, table_name)
        return pd.DataFrame([asdict(r) for r in table.values()])

    def export_csv(self, root: str | Path = ".") -> list[Path]:
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        written = []
        for name in ("preparations", "protocols", "runs", "learning"):
            df = self.to_dataframe(name)
            if not df.empty:
                path = root / f"genesis_{name}.csv"
                df.to_csv(path, index=False)
                written.append(path)
        return written


# ======= Timed additions =======
# One scheduler gives the arm to the next vial due.
# The caller supplies execute(vial, addition) to handle robot movement.

VIAL_STATUSES = ("waiting", "dispensing", "complete", "failed", "aborted")


def load_points(path: str | Path) -> dict[str, list[list[int]]]:
    """Read named [g, s, e, z] routines from a captured points file.

    Single points become one-point routines. Duplicate names use the last
    valid assignment; other assignments are ignored.
    """
    import ast
    tree = ast.parse(Path(path).read_text())
    pts = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        try:
            val = ast.literal_eval(node.value)
        except ValueError:
            continue
        if isinstance(val, list) and len(val) == 4 and all(isinstance(c, (int, float)) for c in val):
            val = [val]                               # Wrap a single point as a routine.
        if (isinstance(val, list) and val
                and all(isinstance(p, list) and len(p) == 4
                        and all(isinstance(c, (int, float)) for c in p) for p in val)):
            pts[node.targets[0].id] = [[int(c) for c in p] for p in val]
    return pts


@dataclass
class Addition:
    """One scheduled step, using a named routine or an inline sequence.

    delay_s is the wait from the previous step's timing anchor, or the
    first step's start offset. source and volume_ml are metadata; label
    sets the display name. dispensed=False excludes drawn volume from
    the preparation's materials.
    """
    routine: str | list
    delay_s: float = 0.0
    source: str = ""
    volume_ml: float = 0.0
    label: str = ""
    dispensed: bool = True

    @property
    def name(self) -> str:
        if self.label:
            return self.label
        return self.routine if isinstance(self.routine, str) else f"inline[{len(self.routine)}]"

    def describe(self) -> str:
        what = f"{self.volume_ml:g} mL {self.source}".strip() if self.volume_ml else self.source
        if what and not self.dispensed:
            what = "draw " + what
        return f"{what} via {self.name}" if what else self.name


@dataclass
class VialPlan:
    """A vial's addition sequence; routines define its physical positions."""
    vial: str
    additions: list[Addition] = field(default_factory=list)
    notes: str = ""


@dataclass
class VialTimeline:
    """Track a vial's next addition, timing, status, and history."""
    plan: VialPlan
    preparation_id: str = ""
    step: int = 0                                     # index of the next addition
    status: str = "waiting"
    due: Optional[float] = None                       # next due time (monotonic)
    due_at: Optional[str] = None                      # due time as an ISO timestamp
    anchor: Optional[float] = None                    # previous start or finish (monotonic)
    history: list[dict] = field(default_factory=list) # one record per attempted addition
    error: str = ""

    @property
    def done(self) -> bool:
        return self.status in ("complete", "failed", "aborted")

    @property
    def next_addition(self) -> Optional[Addition]:
        if self.step < len(self.plan.additions):
            return self.plan.additions[self.step]
        return None


def transfer(src: str, dst: str, ml: float, pump: int = 3, max_ml: float = 1.0,
             fresh_pipette: bool = True) -> list:
    """Build a transfer routine using strokes of at most max_ml.

    src and dst name point arrays; ml is the total volume in mL.
    fresh_pipette adds swap/drop steps, controlled by the runner's
    pipette setting.
    """
    ops = ["swap_pipette"] if fresh_pipette else []
    remaining = float(ml)
    while remaining > 1e-9:
        amount = round(min(remaining, max_ml), 6)
        ops += [src, ("aspirate_ml", pump, amount), dst, ("dispense_ml", pump, amount)]
        remaining -= amount
    if fresh_pipette:
        ops.append("drop_pipette")
    return ops


def draw(src: str, ml: float, pump: int = 3) -> list:
    """Build a routine to draw ml mL from src, without changing the tip."""
    return [src, ("aspirate_ml", pump, float(ml))]


def dispense(dst: str, ml: float, pump: int = 3) -> list:
    """Build a routine to dispense ml mL at dst, without changing the tip."""
    return [dst, ("dispense_ml", pump, float(ml))]


TABLE_COLUMNS = ("Vial", "Source", "From", "To", "mL", "Wait_min", "Repeat", "Routine", "Notes")
TIP_ML = 1.0                                          # tip capacity in mL


def plans_from_table(rows) -> list[VialPlan]:
    """Build vial plans from a DataFrame, row dictionaries, or a table with headers.

    Vial and Wait_min are required; column names ignore case.
    Rows keep their order within each vial. From + To + mL transfers;
    From + mL draws; To + mL dispenses. Routine overrides these.
    Wait_min is the delay in minutes, or the first step's start offset.
    Repeat repeats the row with that delay. Tip changes are added for you.
    Transfers split at TIP_ML; draws and dispenses must fit in one tip.
    Source labels the record; Notes apply to the vial.
    """
    if isinstance(rows, pd.DataFrame):
        df = rows
    else:
        rows = list(rows)
        if rows and isinstance(rows[0], dict):
            df = pd.DataFrame(rows)
        else:
            df = pd.DataFrame(rows[1:], columns=list(rows[0]))
    cols = {str(c).strip().lower(): c for c in df.columns}
    missing = [c for c in ("vial", "wait_min") if c not in cols]
    if missing:
        raise ValueError(f"table needs columns {missing}; have {list(df.columns)}")

    def cell(row, name, default=""):
        c = cols.get(name.lower())
        if c is None:
            return default
        v = row[c]
        if v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == "":
            return default
        return str(v).strip()

    steps: dict = {}                                  # vial -> [(kind, Addition), ...]
    notes: dict = {}
    for i, (_, row) in enumerate(df.iterrows()):
        vial = cell(row, "Vial")
        if not vial:
            raise ValueError(f"row {i}: Vial is required")
        wait_s = 60.0 * float(cell(row, "Wait_min", "0"))
        routine, src, dst = cell(row, "Routine"), cell(row, "From"), cell(row, "To")
        ml = float(cell(row, "mL", "0"))
        source = cell(row, "Source", src or dst or routine)
        repeat = int(float(cell(row, "Repeat", "1")))
        where = f"row {i} ({vial})"
        if routine:
            make = lambda: ("routine", Addition(routine, wait_s, source, ml))
        elif src and dst and ml > 0:
            make = lambda: ("transfer", Addition(transfer(src, dst, ml), wait_s, source, ml, label=f"{src}>{dst}"))
        elif src and ml > 0:
            if ml > TIP_ML:
                raise ValueError(f"{where}: a draw can't exceed {TIP_ML} mL (tip capacity)")
            make = lambda: ("draw", Addition(draw(src, ml), wait_s, source, ml, label=src, dispensed=False))
        elif dst and ml > 0:
            if ml > TIP_ML:
                raise ValueError(f"{where}: a dispense can't exceed {TIP_ML} mL (tip capacity)")
            make = lambda: ("dispense", Addition(dispense(dst, ml), wait_s, source, ml, label=dst))
        else:
            raise ValueError(f"{where}: need Routine, From + mL, To + mL, or From + To + mL")
        if repeat < 1:
            raise ValueError(f"{where}: Repeat must be >= 1")
        seq = steps.setdefault(vial, [])
        for _ in range(repeat):
            seq.append(make())
        notes.setdefault(vial, "")
        if not notes[vial]:
            notes[vial] = cell(row, "Notes")

    plans = []
    for vial, seq in steps.items():
        for j, (kind, add) in enumerate(seq):
            nxt = seq[j + 1][0] if j + 1 < len(seq) else None
            if kind == "draw":
                add.routine = ["swap_pipette"] + add.routine
            elif kind == "dispense" and nxt in (None, "draw", "transfer"):
                add.routine = add.routine + ["drop_pipette"]
        plans.append(VialPlan(vial, [add for _, add in seq], notes[vial]))
    return plans


def plans_from_csv(path_or_text: str | Path) -> list[VialPlan]:
    """Read vial plans from a CSV path or text containing a newline.

    Spaces after commas are ignored; # starts a comment.
    """
    import io
    text = str(path_or_text)
    src = io.StringIO(text.strip() + "\n") if "\n" in text else path_or_text
    return plans_from_table(pd.read_csv(src, skipinitialspace=True, comment="#"))


class TimedFormulation(threading.Thread):
    """Schedule vial additions on one arm in a background thread.

    execute(vial, addition) runs each step. Delays count from the previous
    step's finish, or its start when anchor="start". Lateness is logged;
    each new delay uses the actual start or finish time.
    Each vial gets a Preparation with an addition log. Stopping lets the
    current step finish, then aborts queued steps. Errors stop the schedule
    unless continue_on_error=True, which fails only that vial.
    on_finish(self) runs on the worker thread when the schedule ends.
    """

    def __init__(self, execute: Callable[[str, Addition], Optional[dict]],
                 plans: list[VialPlan], db: Optional[GenesisDB] = None,
                 operator_id: str = "", log_path: str | Path | None = None,
                 continue_on_error: bool = False,
                 on_finish: Optional[Callable[["TimedFormulation"], None]] = None,
                 anchor: str = "finish"):
        super().__init__(name="TimedFormulation")
        if anchor not in ("finish", "start"):
            raise ValueError(f"anchor must be 'finish' or 'start', got {anchor!r}")
        self.anchor = anchor
        self.execute = execute
        self.db = db if db is not None else GenesisDB()
        self.operator_id = operator_id
        self.log_path = Path(log_path) if log_path else None
        self.continue_on_error = continue_on_error
        self.on_finish = on_finish
        self.timelines: dict[str, VialTimeline] = {}
        self._heap: list = []                         # (due, seq, vial)
        self._seq = count()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()                 # protects status reads
        for plan in plans:
            if plan.vial in self.timelines:
                raise ValueError(f"duplicate vial {plan.vial!r}")
            if not plan.additions:
                raise ValueError(f"vial {plan.vial!r} has no additions")
            totals: dict = {}
            for a in plan.additions:
                if a.source and a.dispensed:
                    totals[a.source] = round(totals.get(a.source, 0.0) + a.volume_ml, 6)
            prep = self.db.add(Preparation(
                operator_id=operator_id, method="timed_addition", materials=totals,
                params={"vial": plan.vial, "status": "waiting",
                        "schedule": [self._summary(a) for a in plan.additions], "additions": []},
                notes=plan.notes))
            self.timelines[plan.vial] = VialTimeline(plan=plan, preparation_id=prep.preparation_id)

    @staticmethod
    def _summary(a: Addition) -> dict:
        return {"routine": a.name, "delay_s": a.delay_s, "source": a.source,
                "volume_ml": a.volume_ml, "dispensed": a.dispensed}

    # ----- public -----

    def stop(self) -> None:
        """Finish the current step, then abort queued steps."""
        self._stop_event.set()

    def status(self) -> dict:
        """Return a per-vial snapshot, safe to read from the main thread."""
        now = time.monotonic()
        with self._lock:
            out = {}
            for vial, tl in self.timelines.items():
                nxt = tl.next_addition
                waiting = tl.status == "waiting" and tl.due is not None
                out[vial] = {
                    "status": tl.status, "step": tl.step, "of": len(tl.plan.additions),
                    "next": nxt.describe() if nxt else None,
                    "due_in_s": round(tl.due - now, 1) if waiting else None,
                    "preparation_id": tl.preparation_id, "error": tl.error,
                }
            return out

    def print_status(self) -> None:
        for vial, s in self.status().items():
            if s["due_in_s"] is None:
                when = s["status"]
            elif s["due_in_s"] < 0:
                when = f"overdue {-s['due_in_s']:.0f} s (arm busy)"
            else:
                when = f"due in {s['due_in_s']:.0f} s"
            nxt = f"next {s['next']}: " if s["next"] else ""
            err = f"  [{s['error']}]" if s["error"] else ""
            print(f"{vial} {s['preparation_id']}: {s['step']}/{s['of']} done, {nxt}{when}{err}")

    # ----- scheduler thread -----

    def run(self) -> None:
        t0 = time.monotonic()
        with self._lock:
            for tl in self.timelines.values():
                self._schedule(tl, t0)
        self._log(f"start: {len(self.timelines)} vial(s)")
        try:
            while self._heap and not self._stop_event.is_set():
                due, _, vial = self._heap[0]
                wait = due - time.monotonic()
                if wait > 0:
                    if self._stop_event.wait(wait):   # wakes early on stop()
                        break
                    continue                          # Check the next due time again.
                heapq.heappop(self._heap)
                if not self._do_addition(self.timelines[vial]) and not self.continue_on_error:
                    break
        finally:
            with self._lock:
                for tl in self.timelines.values():
                    if not tl.done:
                        tl.status = "aborted"
                        self._prep(tl).params["status"] = "aborted"
            if self.on_finish is not None:
                try:
                    self.on_finish(self)
                except Exception as e:
                    self._log(f"on_finish FAILED {e!r}")
            self._log("end: " + ", ".join(f"{v}={t.status}" for v, t in self.timelines.items()))

    def _schedule(self, tl: VialTimeline, anchor: float) -> None:
        """Queue the next addition from a monotonic anchor; caller holds _lock."""
        delay = tl.plan.additions[tl.step].delay_s
        tl.due = anchor + delay
        tl.due_at = (datetime.now() + timedelta(seconds=delay)).isoformat(timespec="seconds")
        tl.status = "waiting"
        heapq.heappush(self._heap, (tl.due, next(self._seq), tl.plan.vial))

    def _do_addition(self, tl: VialTimeline) -> bool:
        add = tl.plan.additions[tl.step]
        n = len(tl.plan.additions)
        started = time.monotonic()
        rec = dict(self._summary(add), step=tl.step, due_at=tl.due_at,
                   started_at=datetime.now().isoformat(timespec="seconds"),
                   late_s=round(started - tl.due, 2),
                   since_prev_s=round(started - tl.anchor, 2) if tl.anchor is not None else None)
        with self._lock:
            tl.status = "dispensing"
            self._prep(tl).params["status"] = "dispensing"
        self._log(f"{tl.plan.vial}: {add.describe()} ({tl.step + 1}/{n}, {rec['late_s']:.0f} s late)")
        try:
            result = self.execute(tl.plan.vial, add)
            ok = True
        except Exception as e:                        # run() decides whether to continue.
            result, ok = repr(e), False
        finished = time.monotonic()
        rec.update(finished_at=datetime.now().isoformat(timespec="seconds"),
                   duration_s=round(finished - started, 2), ok=ok, result=result)
        with self._lock:
            tl.history.append(rec)
            self._prep(tl).params["additions"].append(rec)
            if not ok:
                tl.status, tl.error = "failed", str(result)
                self._prep(tl).params["status"] = "failed"
            else:
                tl.step += 1
                tl.anchor = started if self.anchor == "start" else finished
                if tl.step < n:
                    self._schedule(tl, tl.anchor)
                else:
                    tl.status, tl.due, tl.due_at = "complete", None, None
                    self._prep(tl).params["status"] = "complete"
        if not ok:
            self._log(f"{tl.plan.vial}: FAILED {result}")
        return ok

    def _prep(self, tl: VialTimeline) -> Preparation:
        return self.db.preparations[tl.preparation_id]

    def _log(self, msg: str) -> None:
        line = f"[genesis] {datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
        print(line)
        if self.log_path:
            try:
                with open(self.log_path, "a") as f:
                    f.write(line + "\n")
            except OSError:
                pass


# ======= Self-test =======

if __name__ == "__main__":
    import tempfile

    db = GenesisDB()

    prep = db.add(Preparation(operator_id="OP-03", method="dropcast"))
    protocol = db.add(TestingProtocol(name="standard PEIS", technique="PEIS",
                                      params={"initial_freq": 20000, "final_freq": 1}))

    run = db.add(Run(
        run_id="RUN-001", campaign_id="CAM-001", device_id="DEV-001",
        cell_id="CELL-004", test_protocol_id="TEST-012",
        start_time=datetime(2026, 8, 13, 10, 0), end_time=datetime(2026, 8, 13, 16, 0),
        operator_id="OP-03", run_status="complete",
        preparation_id=prep.preparation_id,
    ))

    db.add(LearningHistory(run_ids=[run.run_id], model="baseline",
                           outputs={"suggestion": "raise loading"}))

    print(f"[genesis] {len(db.runs)} run(s); {run.run_id}: {run.run_status}, {run.duration_s/3600:.1f} h")

    # Repeated point names use the latest capture.
    pfile = Path(tempfile.mkdtemp()) / "captured_positions.py"
    pfile.write_text(
        "# 2026-08-13 10:00:00\n"
        "A_src = [1000, 2000, 3000, 400]\n"
        "A_src_approach = [1000, 2000, 3000, -825]\n"
        "# 2026-08-13 10:01:00\n"
        "v1_disp = [[1100, 2100, 3100, 500], [1100, 2100, 3100, 300], ]\n"
        "v1_disp = [[1200, 2200, 3200, 500], [1200, 2200, 3200, 300], ]\n"
        "not_a_point = 'skip me'\n")
    pts = load_points(pfile)
    assert pts["A_src"] == [[1000, 2000, 3000, 400]]
    assert pts["v1_disp"] == [[1200, 2200, 3200, 500], [1200, 2200, 3200, 300]]
    assert "not_a_point" not in pts
    print(f"[genesis] points: {sorted(pts)}")

    # Simulate three vials with staggered A, B, C additions.
    def fake_execute(vial, add):
        time.sleep(0.05)                                  # Simulate robot movement.
        return {"routine": add.name}

    plans = plans_from_csv("""
        Vial, Source, From,  To,      mL,  Wait_min
        v1,   A,      A_src, v1_disp, 1.0, 0
        v1,   B,      B_src, v1_disp, 0.5, 0.00333       # 0.2 s, for the test
        v1,   C,      C_src, v1_disp, 2.0, 0.00333
        v2,   A,      A_src, v2_disp, 1.0, 0.00117       # 0.07 s start offset
        v2,   B,      B_src, v2_disp, 0.5, 0.00333
        v2,   C,      C_src, v2_disp, 2.0, 0.00333
        v3,   A,      A_src, v3_disp, 1.0, 0.00233
        v3,   B,      B_src, v3_disp, 0.5, 0.00333
        v3,   C,      C_src, v3_disp, 2.0, 0.00333
    """)
    assert [p.vial for p in plans] == ["v1", "v2", "v3"] and len(plans[0].additions) == 3
    assert plans[0].additions[2].routine == transfer("C_src", "v1_disp", 2.0)
    assert plans[0].additions[2].routine.count(("aspirate_ml", 3, 1.0)) == 2   # 2 mL = two 1 mL strokes
    tf = TimedFormulation(fake_execute, plans, db=db, operator_id="OP-03")
    tf.start()
    time.sleep(0.1)
    tf.print_status()
    tf.join()
    for vial, tl in tf.timelines.items():
        gaps = ", ".join(f"{r['routine']} +{r['since_prev_s']:.2f} s" for r in tl.history[1:])
        print(f"[genesis] {vial} {tl.preparation_id}: {tl.status} ({gaps})")

    # Draw once, then dispense 0.1 mL five times at a fixed interval.
    drip = plans_from_csv("""
        Vial, Source, From,      To,        mL,  Wait_min, Repeat
        d1,   A,      draw_zone, ,          1.0, 0
        d1,   A,      ,          disp_zone, 0.1, 0.002,    5
    """)
    adds = drip[0].additions
    assert len(adds) == 6 and adds[0].routine[0] == "swap_pipette" and not adds[0].dispensed
    assert [a.routine[-1] == "drop_pipette" for a in adds] == [False, False, False, False, False, True]
    tf = TimedFormulation(fake_execute, drip, db=db, anchor="start")
    tf.start()
    tf.join()
    periods = [r["since_prev_s"] for r in tf.timelines["d1"].history[2:]]     # start-to-start intervals
    assert all(abs(x - 0.12) < 0.02 for x in periods), periods
    print(f"[genesis] d1 {tf.timelines['d1'].preparation_id}: {tf.timelines['d1'].status}, "
          f"materials {db.preparations[tf.timelines['d1'].preparation_id].materials}, periods {periods}")

    print(f"[genesis] exported: {[p.name for p in db.export_csv('genesis_logs')]}")