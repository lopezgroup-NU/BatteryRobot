import numpy as np   
import time  
import math
import pyautogui as pag

width, height = pag.size()

translate_arr = [
        [[0,0], 0],
        [[0,1], 0],
        [[0,2], 0],
        [[0,3], 0],
        [[0,4], 0],
        [[0,5], 0],
        [[0,6], 0],
        [[0,7], 0],

        [[1,0], 0],
        [[1,1], 0],
        [[1,2], 0],
        [[1,3], 0],
        [[1,4], 0],
        [[1,5], 0],
        [[1,6], 0],
        [[1,7], 0],

        [[2,0], 0],
        [[2,1], 0],
        [[2,2], 0],
        [[2,3], 0],
        [[2,4], 0],
        [[2,5], 0],
        [[2,6], 0],
        [[2,7], 0],

        [[3,0], 0],
        [[3,1], 0],
        [[3,2], 0],
        [[3,3], 0],
        [[3,4], 0],
        [[3,5], 0],
        [[3,6], 0],
        [[3,7], 0],
        ]

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
    
    for landt_pos in range(0,32):
        if position == translate_arr[landt_pos][0]:
            return translate_arr[landt_pos][1]
    
    return None

def translate_wells_to_app_pos(position):
    """position gets passed in as a scalar, out comes a vector [row,column] position in the app"""

    for well_pos in range(0,32):
        if well_pos == translate_arr[well_pos][1]:
            return translate_arr[well_pos][0]
    
    return None

def start_wells(well_indices):
    """
    Docstring for start_wells
    
    :param well_indices: list of well indices (between 0 and 31) that you want to start
    """
    for index in range(0,len(well_indices)):
        pos_arr = translate_wells_to_app_pos(index)
        pag.moveTo(150+(pos_arr[1]*137), 150+(pos_arr[1]*52), 1)
        pag.click(button="left")
        pag.moveRel(20, 90)
        #pag.click(button="left")