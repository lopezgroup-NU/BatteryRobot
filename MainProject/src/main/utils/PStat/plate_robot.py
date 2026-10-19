# plate_robot.py -- plate rig (triplet): arm fills for the Mux Cycle.
#
# draw:     source approach -> into the vial -> aspirate -> cell approach ->
#           into the cell -> push everything out, at most 1 mL per trip. Same
#           pattern as BatteryRobot.dispense_vol: pump 3, air on top of the
#           liquid, move_pump(3, 0) to empty the tip. One tip for the whole run.
# simulate: 1 mL of air at the source approach, pushed out at each cell's
#           approach. Never goes into the vial or a cell, no tip.
#
# Points live in plate_locations.py. The arm is `rob` from the Thonny shell,
# unless set_robot() was given another object.

import numbers
import sys
import threading
import time
import traceback

try:
    from utils.PStat import plate_locations as LOC
except ImportError:
    import plate_locations as LOC

PUMP = 3                # pipette pump
TIP_ML = 1.0            # one pipette trip
SIMULATE_ML = 1.0       # air per cell in simulate
ASPIRATE_WAIT_S = 3.0   # in the liquid after aspirating (dispense_vol waits 3 s)
DISPENSE_WAIT_S = 3.0   # at the cell after dispensing
MAX_FILL_ML = 5.0       # the dialog refuses bigger draw volumes (typo guard)

_ROBOT = [None]


def set_robot(robot):
    """Use this arm object instead of `rob` from the shell."""
    _ROBOT[0] = robot


def get_robot():
    """set_robot(...) if called, else `rob` from the Thonny shell; None if neither."""
    if _ROBOT[0] is not None:
        return _ROBOT[0]
    rob = getattr(sys.modules.get("__main__"), "rob", None)
    return rob if hasattr(rob, "goto_safe") else None


def cell_label(hw):
    return "{}{}".format(hw // 4 + 1, "ABCD"[hw % 4])


def _point(value, name):
    if not (isinstance(value, (list, tuple)) and len(value) == 4 and
            all(isinstance(v, numbers.Real) for v in value)):
        raise ValueError("{} is {} -- needs [gripper, elbow, shoulder, z]".format(
            name, "not set" if value is None else repr(value)))
    return list(value)


def cell_point(hw):
    if len(LOC.CELL_LOCATIONS) != 24:
        raise ValueError("CELL_LOCATIONS needs 24 rows, has {}".format(len(LOC.CELL_LOCATIONS)))
    return _point(LOC.CELL_LOCATIONS[hw], "CELL_LOCATIONS[{}] ({})".format(hw, cell_label(hw)))


def cell_approach(hw):
    if LOC.CELL_APPROACHES is not None:
        return _point(LOC.CELL_APPROACHES[hw], "CELL_APPROACHES[{}] ({})".format(hw, cell_label(hw)))
    g, e, s, z = cell_point(hw)
    return [g, e, s, z - LOC.APPROACH_LIFT]


def location_problems(mode, cells):
    """Points a draw/simulate run on hardware cells `cells` still needs ([] = ready)."""
    checks = [lambda: _point(LOC.SOURCE_VIAL_APPROACH, "SOURCE_VIAL_APPROACH")]
    if mode == "draw":
        checks.append(lambda: _point(LOC.SOURCE_VIAL, "SOURCE_VIAL"))
    for hw in cells:
        checks.append(lambda hw=hw: (cell_point(hw), cell_approach(hw)))
    problems = []
    for check in checks:
        try:
            check()
        except (ValueError, IndexError, TypeError) as e:
            problems.append(str(e))
    return problems


class _FifoLock(object):
    """The arm, handed out in the order it was asked for (threading.Lock isn't fair)."""

    def __init__(self):
        self._cv = threading.Condition()
        self._next = 0
        self._serving = 0

    def __enter__(self):
        with self._cv:
            ticket = self._next
            self._next += 1
            while ticket != self._serving:
                self._cv.wait()

    def __exit__(self, *exc):
        with self._cv:
            self._serving += 1
            self._cv.notify_all()


class PlateArm(object):
    """One Mux Cycle run's use of the arm. The mux workers call fill(); calls
    are served one at a time, first come, first served."""

    def __init__(self, robot, mode, volume_ml=1.0):
        if mode not in ("draw", "simulate"):
            raise ValueError("mode must be 'draw' or 'simulate', got {!r}".format(mode))
        self.robot = robot
        self.mode = mode
        self.volume_ml = float(volume_ml)
        self.fault = None
        self.on_fault = None    # optional callback(text), called once when the arm faults
        self._lock = _FifoLock()
        self._tip = False
        self._emptied = False
        self._moved = False

    def fill(self, hw, halted=None):
        """Fill hardware cell hw (0-23); blocks until the arm is free. Returns a
        short note, or None when halted() is true once it is this cell's turn."""
        with self._lock:
            if self.fault:
                raise RuntimeError("arm faulted earlier ({})".format(self.fault))
            if halted is not None and halted():
                return None
            try:
                return self._draw(hw) if self.mode == "draw" else self._simulate(hw)
            except Exception as e:
                self.fault = "{}: {!r}".format(cell_label(hw), e)
                traceback.print_exc()           # the real cause, printed once
                if self.on_fault is not None:
                    self.on_fault(self.fault)
                raise

    def _simulate(self, hw):
        rob = self.robot
        source_approach = _point(LOC.SOURCE_VIAL_APPROACH, "SOURCE_VIAL_APPROACH")
        approach = cell_approach(hw)
        self._moved = True
        rob.goto_safe(source_approach)
        if not self._emptied:
            rob.move_pump(PUMP, 0)            # start the run from an empty stroke
            self._emptied = True
        rob.aspirate_ml(PUMP, SIMULATE_ML)    # air only: the tip stays above the vial
        rob.goto_safe(approach)
        rob.move_pump(PUMP, 0)                # push it out above the cell
        time.sleep(DISPENSE_WAIT_S)
        return "simulated ({:g} mL air)".format(SIMULATE_ML)

    def _draw(self, hw):
        rob = self.robot
        source_approach = _point(LOC.SOURCE_VIAL_APPROACH, "SOURCE_VIAL_APPROACH")
        source = _point(LOC.SOURCE_VIAL, "SOURCE_VIAL")
        approach, target = cell_approach(hw), cell_point(hw)
        self._moved = True
        if not self._tip:                     # one tip for the whole run
            rob.check_remove_pipette()
            rob.get_pipette()                 # ends at safe_zone
            rob.move_pump(PUMP, 0)            # fresh dry tip: start from an empty stroke
            self._tip = True
        left, trips = self.volume_ml, 0
        while left > 1e-6:
            amount = round(min(left, TIP_ML), 6)
            rob.goto_safe(source_approach)
            if amount < TIP_ML:
                rob.aspirate_ml(PUMP, round(TIP_ML - amount, 6))   # air on top, as dispense_vol
            rob.goto(source)
            rob.aspirate_ml(PUMP, amount)
            time.sleep(ASPIRATE_WAIT_S)
            rob.goto(source_approach)
            rob.goto_safe(approach)
            rob.goto(target, vel = 10)
            rob.move_pump(PUMP, 0)            # liquid + air out: tip empty
            time.sleep(DISPENSE_WAIT_S)
            rob.goto(approach)
            left = round(left - amount, 6)
            trips += 1
        return "drew {:g} mL ({} trip{})".format(self.volume_ml, trips, "" if trips == 1 else "s")

    def finish(self):
        """End of run: drop the tip (ends at safe_zone) or park. No moves after a fault."""
        with self._lock:
            if self.fault:
                return "ARM FAULT {} -- arm left where it stopped".format(self.fault)
            if self._tip:
                self.robot.remove_pipette()
                self._tip = False
                return "tip dropped"
            if self._moved:
                park = LOC.PARK_LOCATION
                if park is None:
                    try:
                        from Locator import safe_zone as park
                    except ImportError:
                        return ""
                self.robot.goto_safe(park)
                return "parked"
            return ""