from pyautogui import moveTo, dragTo, press, typewrite, click

def run_battery_cycler():
    #make sure LAND system is on screen
    
    # once on LAND page, highlight cells, right click, click start
    moveTo(150, 150, 1)
    dragTo(1250, 570, 1)
    click(button="right")
    moveTo(1300, 550, 1)
    click(button="left")
    
    #run tests

if __name__ == "__main__":
    run_battery_cycler()

    
    
    
    