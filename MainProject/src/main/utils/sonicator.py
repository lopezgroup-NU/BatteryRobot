import atexit
import threading
import time

import serial

BAUD_RATE = 115200
CLICK_S = 0.25
GAP_S = 0.25
HOLD_S = 3.5                    # held press resets the unit's timer to 99 min
DEVICE_MAX_MIN = 99
REARM_MIN = 90                  # restart before the unit's own timer runs out
START_TEMP_C = 23
MIN_TEMP_C, MAX_TEMP_C = 20, 80
FINISH_TOL_S = 0.5

BUTTONS = {                     # name: (board, relay channel)
    "TEMP_DOWN": ("temp", 1),
    "TEMP_UP": ("temp", 2),
    "TEMP_SET": ("temp", 3),
    "TIME_DOWN": ("time", 1),
    "SONICATE": ("time", 2),
    "TIME_UP": ("time", 3),
}


class SonicatorError(Exception):
    pass


class _Stopped(Exception):
    pass


def make_command(channel, closed):
    operation = 0x01 if closed else 0x00
    return bytes((0xA0, channel, operation, (0xA0 + channel + operation) & 0xFF))


def check_minutes(value):
    try:
        minutes = float(value)
    except (TypeError, ValueError):
        minutes = 0.0
    if not 0 < minutes < float("inf"):
        raise SonicatorError("Sonication time must be a number of minutes greater than 0")
    return minutes


def check_temp(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        temp = float(value)
        valid = temp == int(temp) and MIN_TEMP_C <= temp <= MAX_TEMP_C
    except (ValueError, OverflowError):
        valid = False
    if not valid:
        raise SonicatorError(
            f"Temperature must be a whole number from {MIN_TEMP_C} to {MAX_TEMP_C} C, or blank for no heating")
    return int(temp)


class Sonicator:
    def __init__(self, temp_port="COM6", time_port="COM7", start_temp_c=START_TEMP_C, serial_factory=None):
        self.ports = {"temp": temp_port, "time": time_port}
        self.temp_c = start_temp_c
        self.time_min = None
        self.heater_on = False
        self._serial_factory = serial_factory or serial.Serial
        self._ser = {}
        self._port_lock = {"temp": threading.Lock(), "time": threading.Lock()}
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._thread = None
        self._sonicating = False
        self._state, self._result, self._error = "idle", None, None
        self._total_s = self._done_s = 0.0
        self._seg_start = None
        atexit.register(self.close)     # switch the unit off if the program exits mid-run

    def _now(self):
        return time.monotonic()

    def _sleep(self, seconds):
        time.sleep(seconds)

    def _wait(self, seconds):
        return self._cancel.wait(seconds)

    def connect(self):
        for board, port in self.ports.items():
            ser = self._ser.get(board)
            if ser is not None and ser.is_open:
                continue
            try:
                self._ser[board] = self._serial_factory(
                    port=port, baudrate=BAUD_RATE, timeout=1, write_timeout=1)
                for channel in (1, 2, 3):
                    self._relay(board, channel, False)
            except Exception as exc:
                self._close_ports()
                raise SonicatorError(
                    f"Could not open {port}: {exc}. Close the relay button panel or anything else using it."
                ) from exc

    def _relay(self, board, channel, closed):
        ser = self._ser.get(board)
        if ser is None or not ser.is_open:
            raise SonicatorError(f"{self.ports[board]} is not open")
        with self._port_lock[board]:
            ser.write(make_command(channel, closed))
            ser.flush()

    def _close_ports(self):
        for board, ser in list(self._ser.items()):
            if ser is not None and ser.is_open:
                for channel in (1, 2, 3):
                    try:
                        self._relay(board, channel, False)
                    except Exception:
                        pass
                try:
                    ser.close()
                except Exception:
                    pass
        self._ser.clear()

    def close(self):
        self.stop()
        self.wait(30)
        self._close_ports()

    def _press(self, name, seconds):
        board, channel = BUTTONS[name]
        try:
            self._relay(board, channel, True)
            self._sleep(seconds)
        finally:
            self._relay(board, channel, False)

    def click(self, name):
        self._press(name, CLICK_S)
        self._sleep(GAP_S)

    def set_temperature(self, target_c):
        target = check_temp(target_c)
        if target is None:
            raise SonicatorError("No temperature given")
        if not self.heater_on:
            self.click("TEMP_SET")
            self.heater_on = True
        button, step = ("TEMP_UP", 1) if target > self.temp_c else ("TEMP_DOWN", -1)
        while self.temp_c != target:
            self._check_stop()
            self.click(button)
            self.temp_c += step

    def reset_time(self):
        if self._sonicating:
            raise SonicatorError("Can't reset the timer while the sonicator is running")
        self._press("SONICATE", HOLD_S)
        self._sleep(GAP_S)
        self.time_min = DEVICE_MAX_MIN

    def start(self, minutes, temp_c=None):
        total_s = check_minutes(minutes) * 60.0
        temp_c = check_temp(temp_c)
        with self._lock:
            if self._state != "idle":
                raise SonicatorError("The sonicator is already running")
            self._state = "prepping"
        try:
            self.connect()
        except Exception:
            self._set_state("idle")
            raise
        self._cancel.clear()
        with self._lock:
            self._result = self._error = None
            self._total_s, self._done_s, self._seg_start = total_s, 0.0, None
        self._thread = threading.Thread(target=self._run, args=(total_s, temp_c), daemon=True)
        self._thread.start()

    def stop(self):
        self._cancel.set()

    def wait(self, timeout=None):
        if self._thread is not None:
            self._thread.join(timeout)

    def sonicate(self, minutes, temp_c=None):
        self.start(minutes, temp_c)
        self.wait()
        snap = self.snapshot()
        if snap["error"]:
            raise SonicatorError(snap["error"])
        return snap["result"]

    def snapshot(self):
        with self._lock:
            elapsed = self._done_s
            if self._seg_start is not None:
                elapsed += self._now() - self._seg_start
            return {
                "state": self._state,
                "running": self._state != "idle",
                "remaining_s": max(self._total_s - elapsed, 0.0),
                "result": self._result,
                "error": self._error,
            }

    def _set_state(self, state):
        with self._lock:
            self._state = state

    def _check_stop(self):
        if self._cancel.is_set():
            raise _Stopped()
        

    def _run(self, total_s, temp_c):
        result, problems = "completed", []
        try:
            self._do_run(total_s, temp_c)
        except _Stopped:
            result = "stopped"
        except Exception as exc:
            result, problems = "error", [str(exc)]
        try:
            problems += self._cleanup()
        finally:
            with self._lock:
                self._result = "error" if problems else result
                self._error = "; ".join(problems) or None
                self._state = "idle"

    def _do_run(self, total_s, temp_c):
        if temp_c is not None:
            self.set_temperature(temp_c)
        self._check_stop()
        if self.time_min != DEVICE_MAX_MIN:
            self.reset_time()
        while True:
            self._check_stop()
            self._begin_segment()
            cancelled = self._wait(min(total_s - self._done_s, REARM_MIN * 60.0))
            self._freeze_clock()
            if cancelled:
                raise _Stopped()
            if self._done_s >= total_s - FINISH_TOL_S:
                return
            self._set_state("rearming")
            self._end_sonication()
            self.reset_time()

    def _begin_segment(self):
        self._press("SONICATE", CLICK_S)
        with self._lock:
            self._sonicating = True
            self.time_min = None
            self._seg_start = self._now()
            self._state = "sonicating"

    def _end_sonication(self):
        self.click("SONICATE")
        self._sonicating = False

    def _heater_off(self):
        self.click("TEMP_SET")
        self.heater_on = False

    def _freeze_clock(self):
        with self._lock:
            if self._seg_start is not None:
                self._done_s += self._now() - self._seg_start
                self._seg_start = None

    def _cleanup(self):
        problems = []

        def attempt(action, message):
            try:
                action()
            except Exception as exc:
                problems.append(f"{message} ({exc})")

        self._freeze_clock()
        self._set_state("finishing")
        if self._sonicating:
            attempt(self._end_sonication, "COULD NOT STOP THE SONICATOR - switch it off by hand")
        if self.heater_on:
            attempt(self._heater_off, "could not switch the heater off")
        if not self._sonicating and self.time_min != DEVICE_MAX_MIN:
            attempt(self.reset_time, "could not reset the timer to 99")
        return problems