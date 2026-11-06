# A few notes:
# When holding down "TIME", it defaults to 99 minutes
# Timing sonicator: any t < 99, have internal thread count time until done. Reset to 99 after
# Temp: just click temp on and off
# COM6: 1 (Down), 2 (UP), 3 (TEMP)
# COM7: 1 (Down), 2 (TIME), 3 (UP)

import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import serial

BAUD_RATE = 115200
PULSE_MS = 250

# Use the exact requested physical button mapping.
CHANNELS = {
    "COM6": {"UP": 2, "DOWN": 1, "ON": 3},
    "COM7": {"UP": 3, "DOWN": 1, "ON": 2},
}


def make_command(channel, enabled):
    """Return the 4-byte Diustou USB relay frame."""
    if not 1 <= channel <= 8:
        raise ValueError("Relay channel must be 1-8")
    operation = 0x01 if enabled else 0x00
    checksum = (0xA0 + channel + operation) & 0xFF
    return bytes((0xA0, channel, operation, checksum))


class RelayPanel(tk.Frame):
    """Embed in either a Tk root (standalone) or a Toplevel (popup)."""

    def __init__(self, master, pulse_ms=PULSE_MS):
        tk.Frame.__init__(self, master, bg="white", width=760, height=450)
        self.pack(fill="both", expand=True)
        self.pack_propagate(False)
        self.master.title("Triplet - USB Relay Button Panel")
        self.master.geometry("760x450")
        self.master.resizable(False, False)

        self.pulse_ms = int(pulse_ms)
        self._serials = {port: None for port in CHANNELS}
        self._locks = {port: threading.Lock() for port in CHANNELS}
        self._active = set()               # (port, channel)
        self._result_queue = queue.Queue()  # worker -> Tk UI
        self._buttons = {}                  # (port, channel) -> tk.Button
        self._display_ids = {}              # (port, index) -> canvas text id
        self._status_labels = {}
        self._closing = False

        self._draw_layout()
        for port in CHANNELS:
            self._connect(port, show_error=False)
        self.master.protocol("WM_DELETE_WINDOW", self.close)
        self.after(50, self._poll_results)

    def _draw_layout(self):
        canvas = tk.Canvas(self, width=760, height=405, bg="white",
                           highlightthickness=0)
        canvas.place(x=0, y=0)
        self._canvas = canvas

        # A pair of two-cell readouts: empty until set_display() is called.
        locations = {
            "COM6": {"rect_x": 22, "up_x": 98, "down_x": 230, "on_x": 164},
            "COM7": {"rect_x": 379, "up_x": 455, "down_x": 587, "on_x": 521},
        }
        for port, loc in locations.items():
            x = loc["rect_x"]
            w, y, h = 344, 54, 112
            canvas.create_text(x + w // 2, 32, text=port,
                               font=("Segoe UI", 12, "bold"), fill="black")
            canvas.create_rectangle(x, y, x + w, y + h,
                                    outline="black", width=4)
            canvas.create_line(x + w / 2, y, x + w / 2, y + h,
                               fill="black", width=4)
            for index in range(2):
                cell_x = x + (w / 4 if index == 0 else 3 * w / 4)
                text_id = canvas.create_text(cell_x, y + h / 2,
                                             text="", font=("Segoe UI", 26))
                self._display_ids[(port, index)] = text_id

            self._add_button(port, "UP", loc["up_x"], 224)
            self._add_button(port, "DOWN", loc["down_x"], 224)
            self._add_button(port, "ON", loc["on_x"], 320)

        self._status_labels["COM6"] = tk.Label(
            self, text="COM6: Connecting...", bg="white",
            fg="#555555", font=("Segoe UI", 10))
        self._status_labels["COM6"].place(x=22, y=411)
        self._status_labels["COM7"] = tk.Label(
            self, text="COM7: Connecting...", bg="white",
            fg="#555555", font=("Segoe UI", 10))
        self._status_labels["COM7"].place(x=379, y=411)

        tk.Button(self, text="Reconnect", command=self.reconnect,
                  font=("Segoe UI", 9)).place(x=641, y=406,
                                               width=95, height=30)

    def _add_button(self, port, action, x, y):
        channel = CHANNELS[port][action]
        button = tk.Button(
            self, text=action, bg="white", fg="black",
            activebackground="#e6f3ff", relief="solid", bd=2,
            font=("Segoe UI", 10, "bold"),
            command=lambda p=port, c=channel: self.click(p, c),
        )
        button.place(x=x, y=y, width=60, height=60)
        self._buttons[(port, channel)] = button

    def set_display(self, port, left="", right=""):
        """Optional future extension: update the two empty top readouts."""
        if port not in CHANNELS:
            raise ValueError("Expected COM6 or COM7")
        self._canvas.itemconfigure(self._display_ids[(port, 0)], text=str(left))
        self._canvas.itemconfigure(self._display_ids[(port, 1)], text=str(right))

    def _set_port_status(self, port, label, color="black"):
        self._status_labels[port].config(text="{}: {}".format(port, label),
                                         fg=color)

    def _connect(self, port, show_error):
        current = self._serials[port]
        if current is not None and current.is_open:
            return True
        if any(active_port == port for active_port, _ in self._active):
            return False  # Do not replace a connection during a press.

        if current is not None:
            try:
                current.close()
            except Exception:
                pass
        self._serials[port] = None

        try:
            self._serials[port] = serial.Serial(
                port=port, baudrate=BAUD_RATE, timeout=1, write_timeout=1
            )
            # Leave our three momentary outputs in their released state.
            for channel in (1, 2, 3):
                self._send(port, channel, False)
            self._set_port_status(port, "Connected", "#177245")
            return True
        except Exception as exc:
            self._set_port_status(port, "Disconnected", "#b42318")
            if self._serials[port] is not None:
                try:
                    self._serials[port].close()
                except Exception:
                    pass
                self._serials[port] = None
            if show_error:
                messagebox.showerror("{} connection error".format(port),
                                     str(exc), parent=self.master)
            return False

    def reconnect(self):
        if self._closing:
            return
        for port in CHANNELS:
            if not any(p == port for p, _ in self._active):
                self._connect(port, show_error=True)

    def _send(self, port, channel, enabled):
        ser = self._serials[port]
        if ser is None or not ser.is_open:
            raise RuntimeError("{} is disconnected".format(port))
        frame = make_command(channel, enabled)
        with self._locks[port]:
            ser.write(frame)
            ser.flush()
        print("{} CH{} {}: {}".format(
            port, channel, "PRESS" if enabled else "RELEASE",
            " ".join("{:02X}".format(byte) for byte in frame)
        ))

    def click(self, port, channel):
        """Schedule a single 1000-ms button press without freezing Tkinter."""
        if self._closing or (port, channel) in self._active:
            return
        if not self._connect(port, show_error=True):
            return
        self._active.add((port, channel))
        self._buttons[(port, channel)].config(state="disabled", bg="#dddddd")
        self._set_port_status(port, "Pressing CH{}".format(channel), "#2457a7")
        # Non-daemon worker keeps the release attempt alive during normal exit.
        worker = threading.Thread(target=self._pulse_worker,
                                  args=(port, channel), daemon=False)
        worker.start()

    def _pulse_worker(self, port, channel):
        errors = []
        try:
            self._send(port, channel, True)
            time.sleep(self.pulse_ms / 1000.0)
        except Exception as exc:
            errors.append("Press failed: {}".format(exc))
        finally:
            # Always attempt to release, even if press/write/sleep failed.
            try:
                self._send(port, channel, False)
            except Exception as exc:
                errors.append("RELEASE FAILED: {}".format(exc))
            self._result_queue.put((port, channel, "; ".join(errors)))

    def _poll_results(self):
        while True:
            try:
                port, channel, errors = self._result_queue.get_nowait()
            except queue.Empty:
                break
            self._active.discard((port, channel))
            if not self._closing:
                self._buttons[(port, channel)].config(
                    state="normal", bg="white")
            if errors:
                self._set_port_status(port, "Error - check relay", "#b42318")
                messagebox.showerror("Relay command error",
                                     "{} channel {}: {}".format(port, channel, errors),
                                     parent=self.master)
            elif not any(p == port for p, _ in self._active):
                self._set_port_status(port, "Connected", "#177245")

        if self._closing:
            if not self._active:
                self._finish_close()
                return
        self.after(50, self._poll_results)

    def close(self):
        if self._closing:
            return
        self._closing = True
        for button in self._buttons.values():
            button.config(state="disabled")
        if self._active:
            for port in CHANNELS:
                if any(p == port for p, _ in self._active):
                    self._set_port_status(port, "Finishing press...")
            # _poll_results will close the window after all releases finish.
        else:
            self._finish_close()

    def _finish_close(self):
        # Best-effort release of all six mapped buttons before disconnecting.
        for port in CHANNELS:
            ser = self._serials[port]
            if ser is not None:
                try:
                    for channel in (1, 2, 3):
                        try:
                            self._send(port, channel, False)
                        except Exception as exc:
                            print("WARNING: Could not release {} CH{}: {}".format(
                                port, channel, exc))
                finally:
                    try:
                        ser.close()
                    except Exception:
                        pass
                    self._serials[port] = None
        self.master.destroy()


def open_relay_gui(parent, pulse_ms=PULSE_MS):
    """Open as a nonblocking popup from an existing Tkinter application.

    Example:
        popup = open_relay_gui(self.root)
        # If your class is itself a Tk widget: open_relay_gui(self)

    Do not call an additional mainloop() on this popup.
    Returns the RelayPanel instance, which exposes set_display().
    """
    window = tk.Toplevel(parent)
    return RelayPanel(window, pulse_ms=pulse_ms)


if __name__ == "__main__":
    root = tk.Tk()
    RelayPanel(root)
    root.mainloop()
