import numpy as np   
import time  
import math
import pyautogui as pag
import pywinauto

width, height = pag.size()

translate_arr = [
        [[0,0], 0],
        [[0,1], 1],
        [[0,2], 2],
        [[0,3], 3],
        [[0,4], 4],
        [[0,5], 5],
        [[0,6], 6],
        [[0,7], 7],

        [[1,0], 8],
        [[1,1], 9],
        [[1,2], 10],
        [[1,3], 11],
        [[1,4], 12],
        [[1,5], 13],
        [[1,6], 14],
        [[1,7], 15],

        [[2,0], 16],
        [[2,1], 17],
        [[2,2], 18],
        [[2,3], 19],
        [[2,4], 20],
        [[2,5], 21],
        [[2,6], 22],
        [[2,7], 23],

        [[3,0], 24],
        [[3,1], 25],
        [[3,2], 26],
        [[3,3], 27],
        [[3,4], 28],
        [[3,5], 29],
        [[3,6], 30],
        [[3,7], 31],
        ]

def guarantee_app_start():
    
    #pag.hotkey('winleft', 'r')
    #pag.press('backspace')
    #pag.write(r"c:\Users\llf1362\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\LAND\LANDMon V7.lnk")
    #pag.press('enter')
    #time.sleep(5)
    #pag.hotkey('winleft', 'down')
    #pag.hotkey('winleft', 'up')
    #pag.press('enter')
    
    
    app = pywinauto.Application(backend="uia").start(r"D:\LAND\LANDMon.exe")
    app = pywinauto.Application(backend="uia").connect(title="LAND Battery Testing System - Monitor Software V7.4")
    win = app.window()
    win.maximize()
    """pag.hotkey('winleft', 'down')
    pag.hotkey('winleft', 'down')
    pag.hotkey('winleft', 'down')
    pag.hotkey('winleft', 'down')
    pag.hotkey('winleft', 'down')
    pag.hotkey('winleft', 'up')
    pag.hotkey('winleft', 'up')
    pag.hotkey('winleft', 'up')
    pag.hotkey('winleft', 'up')
    pag.hotkey('winleft', 'down')
    pag.hotkey('winleft', 'up')"""
    #pag.moveTo(1850, 20)
    
    #app_top_window = app.top_window()

    #if app_top_window.is_minimized(): # check if minimized first
    #    app_top_window.restore() 
    #app_top_window.maximize() # ,aximize the window
    #pag.hotkey('winleft', 'up')
    #window = app.top_window()
    #window.restore()
    #window.maximize()
    #window.set_focus()

def start_all_cells():
    pag.hotkey('winleft', 'r')
    pag.press('backspace')
    pag.write(r"c:\Users\llf1362\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\LAND\LANDMon V7.lnk")
    pag.press('enter')
    time.sleep(5)
    pag.hotkey('winleft', 'down')
    pag.hotkey('winleft', 'up')
    pag.press('enter')

    pag.moveTo(150, 150, 1)
    pag.dragTo(1000, 480, 1)
    pag.click(button="right")
    pag.moveTo(1100, 520, 1)
    pag.click(button="left")
    pag.moveTo(1060, 785, 1)
    #pag.click(button="left")

def translate_app_pos_to_wells(position):
    """position gets passed in as [row, column], out comes a scalar position of the well"""
    
    for landt_pos in range(0,31):
        if position == translate_arr[landt_pos][0]:
            return translate_arr[landt_pos][1]
    
    return None

def translate_wells_to_app_pos(position):
    """position gets passed in as a scalar, out comes a vector [row,column] position in the app"""

    for well_pos in range(0,31):
        if position == translate_arr[well_pos][1]:
            return translate_arr[well_pos][0]
    
    return None

def start_wells(well_indices):
    """
    Docstring for start_wells
    
    :param well_indices: list of well indices (between 0 and 31) that you want to start
    """
    guarantee_app_start()
    for index in range(0,len(well_indices)):
        pos_arr = translate_wells_to_app_pos(index)
        pag.moveTo(150+(pos_arr[1]*137), 150+(pos_arr[0]*52), 1)
        pag.click(button="left")
        pag.moveRel(20, 90)
        #pag.click(button="left")