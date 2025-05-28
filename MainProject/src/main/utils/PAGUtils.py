from pyautogui import moveTo, dragTo, click
from pywinauto import Application
import subprocess
import time
from pywinauto import Application
from pathlib import Path

def is_app_running(app_name="LAND Battery Testing System - Monitor Software V7.4"):
    """Check if app window exists and is running"""
    try:
        app = Application(backend="uia").connect(title=app_name)
        return True
    except:
        return False

def ensure_app_visible(app_path=Path(r"C:\Users\llf1362\Desktop\LANDMon V7.lnk"),
                     app_name="LAND Battery Testing System - Monitor Software V7.4",
                     timeout=15):
    """Simply ensures app is visible (launches if not running)"""
    was_open = is_app_running(app_name)
    if not was_open:
        subprocess.Popen(['explorer', str(app_path)], shell=True)
        time.sleep(5)  # Wait for launch
    
    try:
        app = Application(backend="uia").connect(title=app_name)
        window = app.top_window()
        window.restore()
        window.maximize()
        window.set_focus()
        return was_open
    except Exception as e:
        print(f"Warning: Could not focus window - {e}")

def run_battery_cycler():
    #make sure LAND system is on screen
    was_open = ensure_app_visible()

    if not was_open:
        time.sleep(5)
        moveTo(1325, 780, 1)
        click(button="left")

    # once on LAND page, highlight cells, right click, click start
    moveTo(150, 150, 1)
    dragTo(1250, 570, 1)
    click(button="right")
    moveTo(1300, 550, 1)
    click(button="left")
    
if __name__ == "__main__":
    run_battery_cycler()