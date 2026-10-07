import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import time
#from main.utils.BatteryRobotUtils import formulate_in_order

import tkinter as tk
from tkinter import ttk

class ToolTip:
    """Small hover tooltip. tkinter has no built-in one."""
    list_of_components = []

    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip = None
        self._job = None
        # add="+" so this never replaces bindings the widget already has.
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel()
        self._job = self.widget.after(self.delay, self._show)

    def _cancel(self):
        if self._job is not None:
            self.widget.after_cancel(self._job)
            self._job = None

    def _show(self):
        if self.tip is not None:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip = tk.Toplevel(self.widget)
        # No title bar or border — it should look like a tooltip, not a window.
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
        ).pack()

    def _hide(self, _event=None):
        self._cancel()
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None


class FormulationEditor:

    list_of_components = []

    

    def __init__(self, root):
        self.root = root
        root.title("Formulation Editor")
        root.geometry("1200x620")

        self.source_position = tk.StringVar(value="A1")
        self.quantity_var = tk.StringVar()
        self.choice_var = tk.StringVar()
        self.mass_var = tk.StringVar()

        self.addButton = tk.Button(root, text="Add", command=self.on_addButton)
        self.addButton.place(x=350, y=110, width=250, height=30)

        self.chemLabel = tk.Label(root, text="Add Chemical", font=("Helvetica", 11, "bold underline"))
        self.chemLabel.place(x=350, y=20, width=160, height=30)

        self.loc = tk.Entry(root, textvariable=self.source_position)
        self.loc.place(x=350, y=70, width=60, height=30)
        ToolTip(self.loc, "Location; like \"A1\"")

        self.locLabel = tk.Label(root, text="Location", font=("Helvetica", 7))
        self.locLabel.place(x=350, y=50, width=60, height=20)

        self.quantLabel = tk.Label(root, text="Quantity", font=("Helvetica", 7))
        self.quantLabel.place(x=435, y=50, width=60, height=20)

        self.quantity = tk.Entry(root, textvariable=self.quantity_var)
        self.quantity.place(x=420, y=70, width=90, height=30)
        ToolTip(self.quantity, "Integer quantity in microliters; like \"500\"")

        self.separator1 = ttk.Separator(root, orient="vertical")
        self.separator1.place(x=320, y=10, width=20, height=590)

        self.resetButton = tk.Button(root, text="Reset", command=self.on_resetButton)
        self.resetButton.place(x=350, y=150, width=70, height=30)

        self.dleButton = tk.Button(root, text="Delete Selected Entry", command=self.on_dleButton, font=("Helvetica", 7))
        self.dleButton.place(x=440, y=150, width=70, height=30)

        self.formulateButton = tk.Button(root, text="Formulate", command=self.on_formulateButton, font=("Helvetica", 20, "bold"))
        self.formulateButton.place(x=350, y=200, width=160, height=160)

        self.mass_entry = tk.Entry(root, textvariable=self.mass_var)
        self.mass_entry.place(x=520, y=70, width=80, height=30)
        ToolTip(self.mass_entry, "Integer mass in mg")

        self.label9 = tk.Label(root, text="Volume", font=("Helvetica", 7, "bold"))
        self.label9.place(x=445, y=50, width=60, height=20)

        self.label10 = tk.Label(root, text="Mass", font=("Helvetica", 7, "bold"))
        self.label10.place(x=530, y=50, width=60, height=20)

        self.compsLabel = tk.Label(root, text="Procedure", font=("Helvetica", 11, "bold underline"))
        self.compsLabel.place(x=10, y=20, width=130, height=30)


        def move(lb, direction):
            try:
                # Get selected item index
                selected_idx = lb.curselection()[0]
                new_idx = selected_idx + direction
                
                # Check bounds
                if 0 <= new_idx < lb.size():
                    val = lb.get(selected_idx)
                    list_val = self.list_of_components[selected_idx]
                    self.list_of_components.pop(selected_idx)
                    self.list_of_components.insert(new_idx, list_val)
                    lb.delete(selected_idx)
                    lb.insert(new_idx, val)
                    lb.selection_set(new_idx)

                    #print(self.list_of_components)
                    
                    
            except IndexError:
                pass # No item selected

        self.listbox = tk.Listbox(root)
        
        self.listbox.place(x=20, y=60, width=270, height=550)

        
        self.up_button = tk.Button(root, text="^", command=lambda: move(self.listbox, -1), font=("Helvetica", 13))
        self.up_button.place(x=295, y=60, width=20, height=30)

        self.dn_button = tk.Button(root, text="v", command=lambda: move(self.listbox, 1))
        self.dn_button.place(x=295, y=95, width=20, height=30)

        

        self.dispense_rack = tk.LabelFrame(root, text="Dispense Rack", bg="#f6f7fe", relief="groove")
        self.dispense_rack.place(x=350, y=150, width=400, height=270)

        """sy = 10
        self.choice_var.set("0")
        self.radiobutton1 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="A1", bg="#f6f7fe")
        self.radiobutton1.place(x=20, y=20-sy, width=16, height=16)
        ToolTip(self.radiobutton1, "A1")

        self.radiobutton2 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="B1", bg="#f6f7fe")
        self.radiobutton2.place(x=50, y=20-sy, width=16, height=16)
        ToolTip(self.radiobutton2, "B1")

        self.radiobutton3 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="C1", bg="#f6f7fe")
        self.radiobutton3.place(x=80, y=20-sy, width=16, height=16)
        ToolTip(self.radiobutton3, "C1")

        self.radiobutton5 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="A2", bg="#f6f7fe")
        self.radiobutton5.place(x=20, y=50-sy, width=16, height=16)
        ToolTip(self.radiobutton5, "A2")

        self.radiobutton6 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="B2", bg="#f6f7fe")
        self.radiobutton6.place(x=50, y=50-sy, width=16, height=16)
        ToolTip(self.radiobutton6, "B2")

        self.radiobutton7 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="C2", bg="#f6f7fe")
        self.radiobutton7.place(x=80, y=50-sy, width=16, height=16)
        ToolTip(self.radiobutton7, "C2")

        self.radiobutton9 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="A3", bg="#f6f7fe")
        self.radiobutton9.place(x=20, y=80-sy, width=16, height=16)
        ToolTip(self.radiobutton9, "A3")

        self.radiobutton10 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="B3", bg="#f6f7fe")
        self.radiobutton10.place(x=50, y=80-sy, width=16, height=16)
        ToolTip(self.radiobutton10, "B3")

        self.radiobutton11 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="C3", bg="#f6f7fe")
        self.radiobutton11.place(x=80, y=80-sy, width=16, height=16)
        ToolTip(self.radiobutton11, "C3")

        self.radiobutton13 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="A4", bg="#f6f7fe")
        self.radiobutton13.place(x=20, y=110-sy, width=16, height=16)
        ToolTip(self.radiobutton13, "A4")

        self.radiobutton14 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="B4", bg="#f6f7fe")
        self.radiobutton14.place(x=50, y=110-sy, width=16, height=16)
        ToolTip(self.radiobutton14, "B4")

        self.radiobutton15 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="C4", bg="#f6f7fe")
        self.radiobutton15.place(x=80, y=110-sy, width=16, height=16)
        ToolTip(self.radiobutton15, "C4")

        self.radiobutton16 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="D4", bg="#f6f7fe")
        self.radiobutton16.place(x=110, y=110-sy, width=16, height=16)
        ToolTip(self.radiobutton16, "D4")

        self.radiobutton17 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="A5", bg="#f6f7fe")
        self.radiobutton17.place(x=20, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton17, "A2")

        self.radiobutton18 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="B5", bg="#f6f7fe")
        self.radiobutton18.place(x=50, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton18, "A2")

        self.radiobutton19 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="C5", bg="#f6f7fe")
        self.radiobutton19.place(x=80, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton19, "A2")

        self.radiobutton20 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="D5", bg="#f6f7fe")
        self.radiobutton20.place(x=110, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton20, "A2")

        self.radiobutton41 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="E5", bg="#f6f7fe")
        self.radiobutton41.place(x=140, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton41, "A2")

        self.radiobutton42 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="F5", bg="#f6f7fe")
        self.radiobutton42.place(x=170, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton42, "A2")

        self.radiobutton43 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="G5", bg="#f6f7fe")
        self.radiobutton43.place(x=200, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton43, "A2")

        self.radiobutton44 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="H5", bg="#f6f7fe")
        self.radiobutton44.place(x=230, y=140-sy, width=16, height=16)
        ToolTip(self.radiobutton44, "A2")

        self.radiobutton21 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="A6", bg="#f6f7fe")
        self.radiobutton21.place(x=20, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton21, "A2")

        self.radiobutton22 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="B6", bg="#f6f7fe")
        self.radiobutton22.place(x=50, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton22, "A2")

        self.radiobutton23 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="C6", bg="#a6f7ae")
        self.radiobutton23.place(x=80, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton23, "A2")

        self.radiobutton24 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="D6", bg="#f6f7fe")
        self.radiobutton24.place(x=110, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton24, "A2")

        self.radiobutton45 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="E6", bg="#f6f7fe")
        self.radiobutton45.place(x=140, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton45, "A2")

        self.radiobutton46 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="F6", bg="#f6f7fe")
        self.radiobutton46.place(x=170, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton46, "A2")

        self.radiobutton47 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="G6", bg="#f6f7fe")
        self.radiobutton47.place(x=200, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton47, "A2")

        self.radiobutton48 = tk.Radiobutton(self.dispense_rack, text="", variable=self.choice_var, value="H6", bg="#f6f7fe")
        self.radiobutton48.place(x=230, y=170-sy, width=16, height=16)
        ToolTip(self.radiobutton48, "A2")"""

        self.source_rack = tk.LabelFrame(root, text="Source Rack", bg="#f6f7fe", relief="groove")
        self.source_rack.place(x=760, y=150, width=350, height=270)

        """self.radiobuttonS0 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobuttonS0.place(x=40, y=30, width=15, height=15)
        ToolTip(self.radiobuttonS0, "A1")

        self.radiobutton79 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton79.place(x=72, y=30, width=15, height=15)
        ToolTip(self.radiobutton79, "A1")

        self.radiobutton80 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton80.place(x=104, y=30, width=15, height=20)
        ToolTip(self.radiobutton80, "A1")

        self.radiobutton81 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton81.place(x=136, y=30, width=15, height=20)
        ToolTip(self.radiobutton81, "A1")

        self.radiobutton82 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton82.place(x=168, y=30, width=15, height=20)
        ToolTip(self.radiobutton82, "A1")

        self.radiobutton83 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton83.place(x=40, y=62, width=15, height=20)
        ToolTip(self.radiobutton83, "A1")

        self.radiobutton84 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton84.place(x=72, y=62, width=15, height=20)
        ToolTip(self.radiobutton84, "A1")

        self.radiobutton85 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton85.place(x=104, y=62, width=15, height=20)
        ToolTip(self.radiobutton85, "A1")

        self.radiobutton86 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton86.place(x=136, y=62, width=15, height=20)
        ToolTip(self.radiobutton86, "A1")

        self.radiobutton87 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton87.place(x=168, y=62, width=15, height=20)
        ToolTip(self.radiobutton87, "A1")

        self.radiobutton88 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton88.place(x=40, y=94, width=15, height=20)
        ToolTip(self.radiobutton88, "A1")

        self.radiobutton89 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton89.place(x=72, y=94, width=15, height=20)
        ToolTip(self.radiobutton89, "A1")

        self.radiobutton90 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton90.place(x=104, y=94, width=15, height=20)
        ToolTip(self.radiobutton90, "A1")

        self.radiobutton91 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton91.place(x=136, y=94, width=15, height=20)
        ToolTip(self.radiobutton91, "A1")

        self.radiobutton92 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton92.place(x=168, y=94, width=15, height=20)
        ToolTip(self.radiobutton92, "A1")

        self.radiobutton93 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton93.place(x=40, y=126, width=15, height=20)
        ToolTip(self.radiobutton93, "A1")

        self.radiobutton94 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton94.place(x=72, y=126, width=15, height=20)
        ToolTip(self.radiobutton94, "A1")

        self.radiobutton95 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton95.place(x=104, y=126, width=15, height=20)
        ToolTip(self.radiobutton95, "A1")

        self.radiobutton96 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton96.place(x=136, y=126, width=15, height=20)
        ToolTip(self.radiobutton96, "A1")

        self.radiobutton97 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton97.place(x=168, y=126, width=15, height=20)
        ToolTip(self.radiobutton97, "A1")

        self.radiobutton98 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton98.place(x=40, y=158, width=15, height=20)
        ToolTip(self.radiobutton98, "A1")

        self.radiobutton99 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton99.place(x=72, y=158, width=15, height=20)
        ToolTip(self.radiobutton99, "A1")

        self.radiobutton100 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton100.place(x=104, y=158, width=15, height=20)
        ToolTip(self.radiobutton100, "A1")

        self.radiobutton101 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton101.place(x=136, y=158, width=15, height=20)
        ToolTip(self.radiobutton101, "A1")

        self.radiobutton102 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton102.place(x=168, y=158, width=15, height=20)
        ToolTip(self.radiobutton102, "A1")

        self.radiobutton103 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton103.place(x=40, y=190, width=15, height=20)
        ToolTip(self.radiobutton103, "A1")

        self.radiobutton104 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton104.place(x=72, y=190, width=15, height=20)
        ToolTip(self.radiobutton104, "A1")

        self.radiobutton105 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton105.place(x=104, y=190, width=15, height=20)
        ToolTip(self.radiobutton105, "A1")

        self.radiobutton106 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton106.place(x=136, y=190, width=15, height=20)
        ToolTip(self.radiobutton106, "A1")

        self.radiobutton107 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton107.place(x=168, y=190, width=15, height=20)
        ToolTip(self.radiobutton107, "A1")

        self.radiobutton108 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton108.place(x=200, y=30, width=15, height=20)
        ToolTip(self.radiobutton108, "A1")

        self.radiobutton109 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton109.place(x=200, y=62, width=15, height=20)
        ToolTip(self.radiobutton109, "A1")

        self.radiobutton110 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton110.place(x=200, y=94, width=15, height=20)
        ToolTip(self.radiobutton110, "A1")

        self.radiobutton111 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton111.place(x=200, y=126, width=15, height=20)
        ToolTip(self.radiobutton111, "A1")

        self.radiobutton112 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton112.place(x=200, y=158, width=15, height=20)
        ToolTip(self.radiobutton112, "A1")

        self.radiobutton113 = tk.Radiobutton(self.source_rack, text="", variable=self.choice_var, value="1", bg="#f6f7fe")
        self.radiobutton113.place(x=200, y=190, width=15, height=20)
        ToolTip(self.radiobutton113, "A1")"""

        #self.label7 = tk.Label(self.source_rack, text="A ​ ​    B ​ ​   C ​ ​   D ​ ​    E ​ ​    F", bg="#f6f7fe", font=("Helvetica", 11, "bold"))
        #self.label7.place(x=40, y=0, width=180, height=30)

        #self.label8 = tk.Label(self.source_rack, text="1\n\n2\n\n3\n\n4\n\n5\n\n6", bg="#f6f7fe", font=("Helvetica", 11, "bold"))
        #self.label8.place(x=10, y=30, width=20, height=190)

        

        #source_position = tk.StringVar(value="A1")

        COLS = ["A", "B", "C", "D", "E", "F"]
        ROWS = ["1", "2", "3", "4", "5", "6"]

        for col_idx, col_label in enumerate(COLS):
            header = tk.Label(self.source_rack, text=col_label, font=("Arial", 10, "bold"))
            header.grid(row=0, column=col_idx + 1, padx=10, pady=5)

        for r_idx, row_label in enumerate(ROWS):

            header = tk.Label(self.source_rack, text=row_label, font=("Arial", 10, "bold"))
            header.grid(row=r_idx + 1, column=0, padx=10, pady=5)
            
            for c_idx, col_label in enumerate(COLS):
                # Create the position string
                pos_value = f"{col_label}{row_label}"
                
                # Create the radio button
                rb = tk.Radiobutton(
                    self.source_rack, 
                    text=pos_value, 
                    variable=self.source_position, 
                    value=pos_value
                )
                
                # Place it in the grid window (+1 accounts for headers)
                rb.grid(row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)

        self.dispense_position = tk.StringVar(value="A1")
        
        COLS = ["A", "B", "C", "D", "E", "F", "G", "H"]
        ROWS = ["1", "2", "3", "4", "5", "6"]

        for col_idx, col_label in enumerate(COLS):
            header = tk.Label(self.dispense_rack, text=col_label, font=("Arial", 10, "bold"))
            header.grid(row=0, column=col_idx + 1, padx=10, pady=5)

        for r_idx, row_label in enumerate(ROWS):

            header = tk.Label(self.dispense_rack, text=row_label, font=("Arial", 10, "bold"))
            header.grid(row=r_idx + 1, column=0, padx=10, pady=5)
            
            for c_idx, col_label in enumerate(COLS):

                if not ((col_label=="D" or col_label=="E" or col_label=="F" or col_label=="G" or col_label=="H") and int(row_label) < 4) and not ((col_label=="E" or col_label=="F" or col_label=="G" or col_label=="H") and int(row_label) == 4):

                    # Create the position string
                    pos_value = f"{col_label}{row_label}"
                    
                    # Create the radio button
                    rb = tk.Radiobutton(
                        self.dispense_rack, 
                        text=pos_value, 
                        variable=self.dispense_position, 
                        value=pos_value
                    )
                    
                    # Place it in the grid window (+1 accounts for headers)
                    rb.grid(row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)        

    def on_addButton(self):
        root = self.root
        loc = self.source_position.get()
        
        from tkinter import messagebox


        # Define the function to trigger the warning
        def show_warning(text):
            messagebox.showwarning("Error", text)
        
        if self.quantity_var.get() == "" and self.mass_var.get() != "" and loc != "": # if a mass was entered but no volume
                    mass = int(self.mass_var.get())
                    self.list_of_components.append((loc.upper(), mass, 'm'))
                    self.listbox.insert("end", f"{loc.upper()} : {mass}mg")
                    self.loc.delete(0, tk.END)
                    self.mass_entry.delete(0, tk.END)
        elif self.quantity_var.get() != "" and self.mass_var.get() == "" and loc != "": #vice versa
                    quant = int(self.quantity_var.get())
                    self.list_of_components.append((loc.upper(), quant, 'v'))
                    self.listbox.insert("end", f"{loc.upper()} : {quant}uL")
                    self.loc.delete(0, tk.END)
                    self.quantity.delete(0, tk.END)
        elif loc == "":
             show_warning("No location selected!")
        elif self.quantity_var.get() == "" and self.mass_var.get() == "":
                     show_warning("No mass or volume entered!")

    def on_resetButton(self):
        self.listbox.delete(0, tk.END)
        pass

    def on_dleButton(self):
        self.listbox.delete(self.listbox.curselection()[0])
        
        pass

    def on_formulateButton(self):
        #formulate_in_order(self.list_of_components)
        pass

    


    def add_to_list(self, loc = "", quantity = 50, current_list = []):
        current_list.append((loc, quantity))
        return current_list

    
    



def setup_gui():

    root = tk.Tk()
    app = FormulationEditor(root)
    root.mainloop()