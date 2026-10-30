import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import time
import math
import copy
import queue
import threading

import tkinter as tk
from tkinter import ttk
import Locator

DISPENSE_RACK_COORDINATES = {
    "A1": [79, 39521, 25490, 22439],
    "A2": [79, 39441, 28487, 22280],
    "A3": [79, 39117, 30901, 22348],
    "A4": [79, 38786, 33011, 22764],
    "A5": [79, 38046, 34462, 22861],
    "A6": [90, 37168, 35369, 22751],
    "B1": [103, 40830, 26948, 22580],
    "B2": [102, 40764, 30280, 22389],
    "B3": [102, 40479, 33131, 22821],
    "B4": [96, 39806, 35236, 22398],
    "B5": [54, 39063, 37106, 22576],
    "B6": [55, 38213, 38008, 22710],
    "C1": [55, 42180, 28047, 22547],
    "C2": [19, 42096, 32284, 22605],
    "C3": [19, 41744, 36128, 22778],
    "C4": [13, 41023, 38325, 22342],
    "C5": [31, 40192, 40027, 22649],
    "C6": [7, 39207, 40698, 22807],
    "D4": [12, 41964, 41608, 22854],
    "D5": [21, 41029, 42999, 22687],
    "D6": [14, 39906, 43849, 22704],
    "E5": [29, 41709, 47135, 22657],
    "E6": [28, 40518, 47347, 22719],
    "F5": [28, 42052, 51475, 22578],
    "F6": [28, 40815, 50860, 22786],
}

ciara_disp_rack = list(DISPENSE_RACK_COORDINATES.values())

# Rows 1-6, columns A-H; unavailable positions are None.
DISPENSE_RACK_GRID = [
    [DISPENSE_RACK_COORDINATES.get(f"{col}{row}") for col in "ABCDEFGH"]
    for row in range(1, 7)
]

SOURCE_RACK_COORDINATES = {
    "A1": [78, 36087, 41786, 22060],
    "B1": [17, 36525, 44155, 22124],
    "B2": [17, 35034, 43155, 22312],
    "B3": [1, 33363, 41976, 22368],
    "C1": [-109, 36956, 46599, 22221],
    "C2": [-109, 35313, 45454, 22351],
    "C3": [-200, 33698, 43971, 22217],
    "C4": [-316, 31834, 42274, 22377],
    "D1": [-307, 37036, 48825, 22371],
    "D2": [-318, 35503, 47515, 22429],
    "D3": [-319, 33861, 45805, 22246],
    "D4": [-250, 31931, 43991, 22248],
    "D5": [-269, 29834, 41900, 22246],
    "E1": [-268, 37100, 51093, 22428],
    "E2": [-239, 35554, 49401, 22292],
    "E3": [-240, 33860, 47575, 22379],
    "E4": [-231, 31808, 45422, 22253],
    "E5": [-260, 29686, 43060, 22350],
    "F1": [-241, 36825, 52885, 22511],
    "F2": [-241, 35271, 50968, 22380],
    "F3": [-242, 33559, 48994, 22439],
    "F4": [-248, 31763, 46892, 22411],
    "F5": [-312, 29603, 44421, 22396],
}

SOURCE_RACK_GRID = [
    [SOURCE_RACK_COORDINATES.get(f"{col}{row}") for col in "ABCDEF"]
    for row in range(1, 7)
]



columns = ['A', 'B', 'C', 'D', 'E', 'F']
COLS_COUNT = len(columns)

SOURCE_ASPIRATION_COORDINATES = {
    f"{columns[i // COLS_COUNT]}{i % COLS_COUNT + 1}" : Locator.ciara_p_asp[::-1]
    for i in range(len(Locator.ciara_p_asp))
}

SOURCE_ASPIRATION_COORDINATES = {
    "A1": [217, 37665, 46176, 21033],
    # "A1": [1485, 37573, 46167, 21500],
    "B1": [217, 38128, 48743, 21323],
    # "B1": [1550, 38026, 48719, 21500],
    "B2": [199, 36801, 47531, 21192],
    "B3": [193, 35438, 46192, 21181],
}

ciara_source_rack = list(SOURCE_RACK_COORDINATES.values())

SONICATOR_POSITIONS = [
    f"{col}{row}" for col in "ABCD" for row in range(1, 6)
    if not (col in "BC" and row in (2, 3, 4))
]
SONICATOR_DISPENSE_COORDINATES = {
    "A1": [91, 12688, 10260, 8117],
    "A2": [99, 13986, 12502, 7934],
    "A3": [-73, 15381, 14607, 7955],
    "A4": [-1729, 17739, 17815, 7440],
    "B1": [-1768, 11367, 9417, 8000],
    "B5": [-1846, 17895, 19324, 6959],
    "C1": [-1832, 10262, 9175, 7966],
    "C5": [-1514, 15947, 17982, 7224],
    "D1": [-1564, 9333, 9022, 7840],
    "D2": [-1564, 10434, 10953, 7679],
    "D3": [-1562, 11625, 12923, 7566],
    "D4": [-1649, 12881, 14933, 7742],
    "D5": [-1650, 14412, 17081, 7786],
}
SONICATOR_BOTTLES_UNCAPPED = True
CAROUSEL_CAP_HOLDERS = {
    1: {"pickup": None, "approach": None},
    2: {"pickup": None, "approach": None},
}

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

    

    def __init__(self, root, robot):
        self.root = root
        self.robot = robot
        self.list_of_components = []
        root.title("Formulation Editor")
        root.geometry("600x620")

        self.source_position = tk.StringVar(value="A1")
        self.dispense_position = tk.StringVar(value="A1")
        self.quantity_var = tk.StringVar()
        self.choice_var = tk.StringVar()
        self.mass_var = tk.StringVar()
        self.sonicator_source = tk.StringVar(value="A1")
        self.sonicator_position = tk.StringVar(value="A1")
        self.sonicator_amount = tk.StringVar()
        self.sonicator_interval = tk.StringVar()

        # self.chemLabel = tk.Label(root, text="Add Chemical", font=("Helvetica", 11, "bold underline"))
        # self.chemLabel.place(x=350, y=20, width=160, height=30)
        
        
        self.separator1 = ttk.Separator(root, orient="vertical")
        self.separator1.place(x=320, y=10, width=20, height=590)

        self.resetButton = tk.Button(root, text="Reset", command=self.on_resetButton)
        self.resetButton.place(x=140, y=20, width=70, height=30)

        self.dleButton = tk.Button(root, text="Delete Entry", command=self.on_dleButton, font=("Helvetica", 7))
        self.dleButton.place(x=220, y=20, width=70, height=30)

        self.formulateButton = tk.Button(root, text="Formulate", command=self.on_formulateButton, font=("Helvetica", 20, "bold"))
        self.formulateButton.place(x=350, y=300, width=230, height=200)

        

        

        self.compsLabel = tk.Label(root, text="Procedure", font=("Helvetica", 11, "bold underline"))
        self.compsLabel.place(x=10, y=20, width=130, height=30)

        self.action_frame = tk.Frame(root, relief="groove", bd=2)
        self.action_frame.place(x=350, y=20, width=230, height=270)

        self.vial_to_carousel = tk.Button(self.action_frame, text="Move Vial\n to Carousel", command=lambda: move_to_carousel_popup())
        self.vial_to_carousel.place(x=20, y=50, width=90, height=70)

        self.vial_from_carousel = tk.Button(self.action_frame, text="Move Vial\n from Carousel", command=self.on_vial_from_carousel)
        self.vial_from_carousel.place(x=120, y=50, width=90, height=70)

        self.pipette_carousel = tk.Button(self.action_frame, text="Pipette into\n Carousel", command=lambda: add_liquid_popup())
        self.pipette_carousel.place(x=20, y=130, width=90, height=70)

        self.arbitrary_move = tk.Button(self.action_frame, text="Reposition\n Vial", command=lambda: resposition_popup())
        self.arbitrary_move.place(x=120, y=130, width=90, height=70)

        self.sonicate_vial = tk.Button(self.action_frame, text="Sonicate Vial", command=lambda: sonicate_popup())
        self.sonicate_vial.place(x=20, y=210, width=90, height=70)

        self.arbitrary_move = tk.Button(self.action_frame, text="Heat vial", command=lambda: print("nothing here yet"))
        self.arbitrary_move.place(x=120, y=210, width=90, height=70)

        self.action_buttons = tk.Label(self.action_frame, text="Insert Action", font=("Helvetica", 13, "bold"))
        self.action_buttons.place(x=10, y=10, width=210, height=30)

    

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

        
        def move_to_carousel_popup():
            popup = tk.Toplevel(root)
            popup.title("Move Vial To Carousel")
            popup.geometry("760x420")

            xshift = 300
            yshift = 50

            self.loc = tk.Entry(popup, textvariable=self.dispense_position)
            self.loc.place(x=350-xshift, y=70-yshift, width=60, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")

            self.dispense_rack = tk.LabelFrame(popup, text="Dispense Rack", bg="#f6f7fe", relief="groove")
            self.dispense_rack.place(x=350-xshift, y=150-yshift, width=660, height=270)
                        
            COLS = ["A", "B", "C", "D", "E", "F", "G", "H"]
            ROWS = ["1", "2", "3", "4", "5", "6"]

            for col_idx, col_label in enumerate(COLS):
                header = tk.Label(self.dispense_rack, text=col_label, font=("Arial", 10, "bold"))
                header.grid(row=0, column=col_idx + 1, padx=10, pady=5)

            for r_idx, row_label in enumerate(ROWS):

                header = tk.Label(self.dispense_rack, text=row_label, font=("Arial", 10, "bold"))
                header.grid(row=r_idx + 1, column=0, padx=10, pady=5)
                
                for c_idx, col_label in enumerate(COLS):

                    if f"{col_label}{row_label}" in DISPENSE_RACK_COORDINATES:

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

                    else:
                        tk.Label(self.dispense_rack, text="X", fg="gray", relief="sunken", width=4).grid(
                            row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)

            self.addButton = tk.Button(popup, text="Add to Procedure", command=self.on_tocarousel_button)
            self.addButton.place(x=350-xshift, y=110-yshift, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=350-xshift, y=380, width=250, height=30)

        def resposition_popup():
            popup = tk.Toplevel(root)
            popup.title("Reposition Vial")
            popup.geometry("1000x500")

        def sonicate_popup():
            popup = tk.Toplevel(root)
            popup.title("Source to Sonicator")
            popup.geometry("560x440")

            tk.Label(popup, text="Source Rack").place(x=30, y=10, width=110, height=20)
            ttk.Combobox(popup, textvariable=self.sonicator_source,
                         values=list(SOURCE_ASPIRATION_COORDINATES), state="readonly").place(
                             x=30, y=35, width=110, height=30)
            tk.Label(popup, text="Amount (uL)").place(x=165, y=10, width=130, height=20)
            amount_entry = tk.Entry(popup, textvariable=self.sonicator_amount)
            amount_entry.place(x=165, y=35, width=130, height=30)
            ToolTip(amount_entry, "Total volume in uL. A blank amount saves a plan that cannot run yet.")
            tk.Label(popup, text="Interval (seconds)").place(x=320, y=10, width=160, height=20)
            tk.Entry(popup, textvariable=self.sonicator_interval).place(x=320, y=35, width=160, height=30)
            tk.Label(popup, text="Blank interval: one dose. Interval 10: ten doses, 10s after each dose.").place(
                x=20, y=70, width=520, height=20)

            rack = tk.LabelFrame(popup, text="Sonicator", relief="groove")
            rack.place(x=65, y=100, width=430, height=265)
            for col_index, col in enumerate("ABCD", 1):
                tk.Label(rack, text=col, font=("Arial", 10, "bold")).grid(
                    row=0, column=col_index, padx=12, pady=6)
            for row in range(1, 6):
                tk.Label(rack, text=str(row), font=("Arial", 10, "bold")).grid(
                    row=row, column=0, padx=12, pady=6)
                for col_index, col in enumerate("ABCD", 1):
                    position = f"{col}{row}"
                    if position not in SONICATOR_POSITIONS:
                        tk.Label(rack, text="", width=6).grid(row=row, column=col_index)
                        continue
                    if position not in SONICATOR_DISPENSE_COORDINATES:
                        tk.Label(rack, text="X", fg="gray", width=6).grid(row=row, column=col_index)
                        continue
                    tk.Radiobutton(rack, text=position, variable=self.sonicator_position,
                                   value=position).grid(row=row, column=col_index, padx=8, pady=6)

            tk.Button(popup, text="Add to Procedure", command=self.on_sonicator_button).place(
                x=65, y=385, width=210, height=30)
            tk.Button(popup, text="Close", command=popup.destroy).place(
                x=295, y=385, width=200, height=30)
        
        def add_liquid_popup():
            popup = tk.Toplevel(root)
            popup.title("Pipette Liquid into Carousel")
            popup.geometry("600x420")
            xshift = 300
            yshift = 50

            self.loc = tk.Entry(popup, textvariable=self.source_position)
            self.loc.place(x=350-xshift, y=70-yshift, width=60, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")
    
            self.locLabel = tk.Label(popup, text="Location", font=("Helvetica", 7))
            self.locLabel.place(x=350-xshift, y=50-yshift, width=60, height=20)
    
            self.quantity = tk.Entry(popup, textvariable=self.quantity_var)
            self.quantity.place(x=420-xshift, y=70-yshift, width=90, height=30)
            ToolTip(self.quantity, "Integer quantity in microliters; like \"500\"")

            self.mass_entry = tk.Entry(popup, textvariable=self.mass_var)
            self.mass_entry.configure(state="disabled")
            self.mass_entry.place(x=520-xshift, y=70-yshift, width=80, height=30)
            ToolTip(self.mass_entry, "Mass dispensing is not connected to this cap sequence yet.")
            
            #self.dispense_rack = tk.LabelFrame(popup, text="Dispense Rack", bg="#f6f7fe", relief="groove")
            #self.dispense_rack.place(x=350-xshift, y=150-yshift, width=400, height=270)

            self.source_rack = tk.LabelFrame(popup, text="Source Rack", bg="#f6f7fe", relief="groove")
            self.source_rack.place(x=350-xshift, y=150-yshift, width=500, height=270)

            self.label9 = tk.Label(popup, text="Volume (uL)", font=("Helvetica", 7, "bold"))
            self.label9.place(x=420-xshift, y=50-yshift, width=90, height=20)
    
            self.label10 = tk.Label(popup, text="Mass (mg)", font=("Helvetica", 7, "bold"))
            self.label10.place(x=520-xshift, y=50-yshift, width=80, height=20)

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

                    if pos_value not in SOURCE_RACK_COORDINATES:
                        tk.Label(self.source_rack, text="X", fg="gray", relief="sunken", width=4).grid(
                            row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)
                        continue
                    
                    # Create the radio button
                    rb = tk.Radiobutton(
                        self.source_rack, 
                        text=pos_value, 
                        variable=self.source_position, 
                        value=pos_value,
                        state="normal" if pos_value in SOURCE_ASPIRATION_COORDINATES else "disabled"
                    )
                    if pos_value not in SOURCE_ASPIRATION_COORDINATES:
                        ToolTip(rb, "Aspiration coordinates are still needed.")
                    
                    # Place it in the grid window (+1 accounts for headers)
                    rb.grid(row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)
            """
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
                        rb.grid(row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)"""

            self.addButton = tk.Button(popup, text="Add to Procedure", command=self.on_addButton)
            self.addButton.place(x=350-xshift, y=110-yshift, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=350-xshift, y=380, width=250, height=30)
            #close_button.pack(pady=10)
        
        

        self.listbox = tk.Listbox(root)
        
        self.listbox.place(x=20, y=60, width=270, height=535)
        procedure_scroll = tk.Scrollbar(root, orient="horizontal", command=self.listbox.xview)
        procedure_scroll.place(x=20, y=595, width=270, height=15)
        self.listbox.configure(xscrollcommand=procedure_scroll.set)

        
        self.up_button = tk.Button(root, text="^", command=lambda: move(self.listbox, -1), font=("Helvetica", 13))
        self.up_button.place(x=295, y=60, width=20, height=30)

        self.dn_button = tk.Button(root, text="v", command=lambda: move(self.listbox, 1))
        self.dn_button.place(x=295, y=95, width=20, height=30)

        

    def on_vial_to_carousel(self):
        #self.open_popup()
        pass
    
    def on_vial_from_carousel(self):
        pass

    def on_pipette_carousel(self):
        pass

    def on_arbitrary_move(self):
        pass

    def on_addButton(self):
        
        loc = self.source_position.get().strip().upper()
        volume = self.quantity_var.get().strip()
        mass = self.mass_var.get().strip()
        
        from tkinter import messagebox


        # Define the function to trigger the warning
        def show_warning(text):
            messagebox.showwarning("Error", text)
        
        if loc not in SOURCE_RACK_COORDINATES:
            show_warning("Select a source rack position with known coordinates.")
            return
        if loc not in SOURCE_ASPIRATION_COORDINATES:
            show_warning("Aspiration coordinates are available only for A1 and B1-B3.")
            return
        if not volume and not mass:
            show_warning("Enter a volume (uL).")
            return
        if volume and mass:
            show_warning("Both mass and volume entered; only one can be chosen!")
            return
        if mass:
            show_warning("Mass dispensing is not connected to this cap sequence yet.")
            return

        try:
            amount = int(volume or mass)
        except ValueError:
            show_warning("Volume must be a positive whole number in uL.")
            return
        if amount <= 0:
            show_warning("Volume must be a positive whole number in uL.")
            return

        mode = 'v' if volume else 'm'
        unit = 'uL' if volume else 'mg'
        self.list_of_components.append(("pipette_into_carousel", f"s{loc}", amount, mode))
        self.listbox.insert("end", f"Source {loc}: {amount}{unit} -> Carousel")
        self.source_position.set("")
        self.quantity_var.set("")
        self.mass_var.set("")

    def on_tocarousel_button(self):
        
        loc = self.dispense_position.get().strip().upper()
        if loc not in DISPENSE_RACK_COORDINATES:
            messagebox.showwarning("Error", "Select a valid dispense rack position.")
            return

        self.list_of_components.append(("move_vial_to_carousel", f"d{loc}", '', ''))
        self.listbox.insert("end", f"Dispense Rack {loc} -> Carousel")
        self.dispense_position.set("")

    def on_sonicator_button(self):
        source = self.sonicator_source.get().strip().upper()
        destination = self.sonicator_position.get().strip().upper()
        amount_text = self.sonicator_amount.get().strip()
        interval_text = self.sonicator_interval.get().strip()
        if source not in SOURCE_RACK_COORDINATES or source not in SOURCE_ASPIRATION_COORDINATES:
            messagebox.showwarning("Error", "Select a source with known aspiration coordinates.")
            return
        if destination not in SONICATOR_DISPENSE_COORDINATES:
            messagebox.showwarning("Error", "Select a calibrated sonicator position; A5 is unavailable.")
            return
        try:
            amount = int(amount_text) if amount_text else None
            interval = int(interval_text) if interval_text else None
            if (amount is not None and amount <= 0) or (interval is not None and interval <= 0):
                raise ValueError
        except ValueError:
            messagebox.showwarning("Error", "Amount and interval must be positive whole numbers, or blank.")
            return
        setting = {"destination": destination, "interval": interval}
        self.list_of_components.append(("pipette_into_sonicator", f"s{source}", amount, setting))
        description = f"Source {source} -> Sonicator {destination}"
        if amount is None:
            description += ": amount not set"
            if interval is not None:
                description += f"; {interval} doses, {interval}s wait"
        elif interval is None:
            description += f": {amount}uL once"
        else:
            description += f": {interval} x {amount / interval:g}uL; {interval}s wait"
        self.listbox.insert("end", description)
        # self.sonicator_amount.set("")
        self.sonicator_amount.set(1000) #idk why the input is not getting passed in
        self.sonicator_interval.set("")
       


    def on_resetButton(self):
        self.listbox.delete(0, tk.END)
        self.list_of_components = []
        pass

    def on_dleButton(self):
        selected = self.listbox.curselection()
        if not selected:
            return
        index = selected[0]
        self.list_of_components.pop(index)
        self.listbox.delete(index)

    def on_formulateButton(self):
        if getattr(self, "_running", False) or not self.list_of_components:
            return
        actions = copy.deepcopy(self.list_of_components)
        result = queue.Queue()
        self._running = True
        self.formulateButton.configure(state="disabled", text="Running...")

        def work():
            try:
                run_formulation(self.robot, actions)
            except Exception as error:
                result.put(str(error))
            else:
                result.put(None)

        def finish():
            try:
                error = result.get_nowait()
            except queue.Empty:
                self.root.after(100, finish)
                return
            self._running = False
            self.formulateButton.configure(state="normal", text="Formulate")
            if error is not None:
                messagebox.showerror("Cannot formulate", error)

        threading.Thread(target=work).start()
        self.root.after(100, finish)
        

    


    def add_to_list(self, loc = "", quantity = 50, current_list = []):
        current_list.append((loc, quantity))
        return current_list

    
    



def _float_ulp(value):
    value = abs(float(value))
    if not math.isfinite(value):
        return value
    if value == 0:
        return math.ldexp(1.0, -1074)
    return math.ldexp(1.0, max(math.frexp(value)[1] - 53, -1074))


def _positive_volume(value):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value <= 0):
        raise ValueError("Volume must be a positive finite number in microliters.")
    return float(value)


def _loaded_volume(robot):
    if not getattr(robot, "holding_pipette", False):
        raise ValueError("A pipette must be attached before moving liquid.")
    loaded = getattr(robot, "_pipette_liquid_ul", None)
    if (isinstance(loaded, bool) or not isinstance(loaded, (int, float))
            or not math.isfinite(loaded) or loaded < 0):
        raise ValueError("The liquid amount in the pipette is unknown.")
    return float(loaded)


def _draw_liquid(robot, aspiration_pose, volume_ul):
    amount = _positive_volume(volume_ul)
    loaded = _loaded_volume(robot)
    available = 1000.0 - loaded
    tolerance = 4 * max(_float_ulp(1000.0), _float_ulp(loaded), _float_ulp(amount))
    if available <= 0 or amount > available + tolerance:
        raise ValueError("The pipette cannot hold more than 1000 microliters.")
    amount = min(amount, available)
    robot.goto_safe(aspiration_pose, vel=8)
    try:
        robot.aspirate_ml(3, amount / 1000)
    except BaseException:
        robot._pipette_liquid_ul = None
        raise
    robot._pipette_liquid_ul = loaded + amount


def _dispense_liquid(robot, volume_ul):
    amount = _positive_volume(volume_ul)
    loaded = _loaded_volume(robot)
    # Never dispense from an empty pipette.
    if loaded <= 0:
        raise ValueError("The pipette is empty; aspirate liquid before dispensing.")
    tolerance = 4 * max(_float_ulp(loaded), _float_ulp(amount))
    if amount > loaded + tolerance:
        raise ValueError("The requested dispense exceeds the pipette's loaded liquid.")
    amount = min(amount, loaded)
    try:
        robot.dispense_ml(3, amount / 1000)
    except BaseException:
        robot._pipette_liquid_ul = None
        raise
    remaining = loaded - amount
    robot._pipette_liquid_ul = 0.0 if remaining <= tolerance else remaining
    return time.monotonic()


def _transfer_source(robot, source_pose, aspiration_pose, destination_pose,
                     total_ul, dose_count, interval_s, safe_pose):
    total = _positive_volume(total_ul)
    if isinstance(dose_count, bool) or not isinstance(dose_count, int) or dose_count < 1:
        raise ValueError("Dose count must be a positive integer.")
    if (isinstance(interval_s, bool) or not isinstance(interval_s, (int, float))
            or not math.isfinite(interval_s) or interval_s < 0):
        raise ValueError("The dose interval must be a finite, nonnegative number of seconds.")
    if getattr(robot, "holding_pipette", False) or getattr(robot, "holding_vial", False):
        raise ValueError("Start the transfer with an empty pipette mount and claw.")
    pip_id = getattr(robot, "pip_id", None)
    if isinstance(pip_id, bool) or not isinstance(pip_id, int) or not 0 <= pip_id < 48:
        raise ValueError("No unused pipette is selected in the 48-position rack.")
    available = 48 - pip_id
    needed = math.ceil(total / 1000.0)
    if needed > available:
        raise ValueError("Not enough unused pipettes remain for all draws.")
    loads = [1000.0] * (needed - 1)
    loads.append(math.fsum((total, -1000.0 * (needed - 1))))
    nominal_dose = _positive_volume(total / dose_count)
    final_dose = _positive_volume(math.fsum((total, -nominal_dose * (dose_count - 1))))

    def finish_load():
        try:
            robot.remove_pipette()
        except BaseException:
            robot._pipette_liquid_ul = None
            raise
        robot._pipette_liquid_ul = 0.0
        robot.goto_safe(source_pose, vel=8)
        robot.cap()
        robot.open_gripper()
        robot.goto_safe(safe_pose)

    load_index, load_active = 0, False
    previous_completion = None
    for dose_index in range(dose_count):
        dose = nominal_dose if dose_index < dose_count - 1 else final_dose
        dose_parts, remaining, first_part = [], dose, True
        while remaining > 0:
            if not load_active:
                if load_index >= len(loads):
                    raise RuntimeError("The planned liquid was exhausted before the dose completed.")
                load_volume = loads[load_index]
                load_index += 1
                robot.goto_safe(source_pose, vel=8)
                robot.close_gripper()
                robot.delay(0.5)
                robot.uncap(pitch=1.35, revs=7)

                last_pipette = robot.pip_id == 47
                robot._pipette_liquid_ul = None
                try:
                    robot.get_pipette()
                finally:
                    if last_pipette:
                        robot.pip_id = 48  # Never wrap to an already-used pipette.
                robot._pipette_liquid_ul = 0.0
                _draw_liquid(robot, aspiration_pose, load_volume)
                robot.delay(3)
                robot.goto_safe(destination_pose, vel=8)
                load_parts, load_active = [], True

            loaded = _loaded_volume(robot)
            if loaded <= 0:
                raise RuntimeError("The pipette is empty before the requested dispense.")
            amount = min(remaining, loaded)
            if first_part and previous_completion is not None:
                deadline = previous_completion + interval_s
                while True:
                    wait = deadline - time.monotonic()
                    if wait <= 0:
                        break
                    time.sleep(min(wait, 0.1))
            completion = _dispense_liquid(robot, amount)
            load_parts.append(amount)
            # Avoid accumulated rounding error.
            loaded = math.fsum((load_volume, -math.fsum(load_parts)))
            tolerance = 4 * max(_float_ulp(load_volume), _float_ulp(dose))
            robot._pipette_liquid_ul = 0.0 if loaded <= tolerance else loaded
            dose_parts.append(amount)
            remaining = max(0.0, math.fsum((dose, -math.fsum(dose_parts))))
            if remaining <= tolerance:
                remaining = 0.0
            first_part = False

            if robot._pipette_liquid_ul == 0:
                robot.delay(3)
                finish_load()
                load_active = False
        previous_completion = completion

    if load_active:
        # Dispose of any rounding residue.
        robot.delay(3)
        finish_load()


def run_formulation(robot, actions):
    if not actions:
        return
    if getattr(robot, "_formulation_recovery_required", False):
        raise RuntimeError("The previous run stopped. Restore the caps, pipette and pump state, then clear _formulation_recovery_required on this robot before retrying.")

    current_vial = getattr(robot, "_formulation_carousel_position", None)
    pipettes_needed = 0
    uses_carousel = False
    plans = []

    def check_point(point, name):
        if not isinstance(point, (list, tuple)) or len(point) != 4 or not all(
                isinstance(n, (int, float)) and math.isfinite(n) for n in point):
            raise ValueError(f"A calibrated {name} position is required.")

    for action in actions:
        if not isinstance(action, (list, tuple)) or len(action) != 4:
            raise ValueError("Each procedure entry must contain four values.")
        name, location, value, setting = action
        if name == "move_vial_to_carousel":
            if not isinstance(location, str) or not location.startswith('d') or location[1:] not in DISPENSE_RACK_COORDINATES:
                raise ValueError(f"No dispense rack coordinates for {location!r}.")
            if current_vial is not None:
                raise ValueError("Only one vial can occupy the carousel. After manually removing it, set the robot's _formulation_carousel_position to None before loading another.")
            current_vial = location[1:]
            check_point(DISPENSE_RACK_COORDINATES[current_vial], f"dispense rack {current_vial}")
            uses_carousel = True
            plans.append((name, current_vial, None, 0, 1, 0))
            continue
        if name not in ("pipette_into_carousel", "pipette_into_sonicator"):
            raise ValueError(f"Unsupported action: {name!r}.")
        if not isinstance(location, str) or not location.startswith('s') or location[1:] not in SOURCE_RACK_COORDINATES:
            raise ValueError(f"No source rack coordinates for {location!r}.")
        source = location[1:]
        if source not in SOURCE_ASPIRATION_COORDINATES:
            raise ValueError(f"No aspiration coordinates for {source}.")
        check_point(SOURCE_RACK_COORDINATES[source], f"source {source}")
        check_point(SOURCE_ASPIRATION_COORDINATES[source], f"source {source} aspiration")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Enter a positive amount in microliters before Formulate. Delete and re-add entries with an unset amount.")

        count, interval, target = 1, 0, None
        if name == "pipette_into_carousel":
            if current_vial is None:
                raise ValueError("Add Move Vial to Carousel before adding liquid to it.")
            if setting != 'v':
                raise NotImplementedError("This cap sequence currently supports volume dispensing only.")
            uses_carousel = True
        else:
            if not isinstance(setting, dict):
                raise ValueError("The sonicator entry needs a destination and interval setting.")
            target = setting.get("destination")
            if target not in SONICATOR_DISPENSE_COORDINATES:
                raise ValueError(f"No sonicator dispensing coordinates for {target!r}.")
            check_point(SONICATOR_DISPENSE_COORDINATES[target], f"sonicator {target}")
            if SONICATOR_BOTTLES_UNCAPPED is not True:
                raise ValueError("The receiving sonicator bottles must already be uncapped.")
            entered_interval = setting.get("interval")
            if entered_interval is not None:
                if isinstance(entered_interval, bool) or not isinstance(entered_interval, int) or entered_interval <= 0:
                    raise ValueError("The sonicator interval must be a positive whole number of seconds, or blank.")
                count = interval = entered_interval
        pipettes_needed += math.ceil(value / 1000)
        plans.append((name, source, target, value, count, interval))

    if robot.holding_pipette or robot.holding_vial:
        raise ValueError("The robot must start with an empty pipette mount and claw.")
    if pipettes_needed and (not isinstance(robot.pip_id, int) or robot.pip_id < 0 or robot.pip_id + pipettes_needed > 48):
        raise ValueError(f"This procedure needs {pipettes_needed} fresh pipettes; not enough remain in the 48-position rack.")

    import Locator

    required = ["safe_zone"]
    holder = None
    if uses_carousel:
        for holder_id, positions in CAROUSEL_CAP_HOLDERS.items():
            if positions["pickup"] is not None and positions["approach"] is not None and getattr(robot, f"cap_holder_{holder_id}_free", False):
                check_point(positions["pickup"], f"cap holder {holder_id} pickup")
                check_point(positions["approach"], f"cap holder {holder_id} approach")
                holder, holder_positions = holder_id, positions
                break
        if holder is None:
            raise ValueError("Carousel actions need updated pickup and approach coordinates for a free cap holder. The old Locator.py holder positions are not used.")
        required += ["vial_carousel", "vial_carousel_approach"]
    if any(plan[0] == "pipette_into_carousel" for plan in plans):
        required.append("carousel_dispense")
    if pipettes_needed:
        required += ["p_remover_capture", "p_remover_capture_approach"]
    for name in required:
        check_point(getattr(Locator, name, None), f"Locator.{name}")
    if pipettes_needed:
        grid = getattr(Locator, "pipette_grid", None)
        if not isinstance(grid, (list, tuple)) or len(grid) != 48:
            raise ValueError("The existing 48-position pipette_grid is required in Locator.py.")
        for index, point in enumerate(grid):
            check_point(point, f"pipette {index}")

    stage = "starting the procedure"
    carousel_open = False
    robot._formulation_recovery_required = True
    try:
        for name, source, target, total, count, interval in plans:
            if name == "move_vial_to_carousel":
                stage = "moving the vial to the carousel"
                robot._formulation_carousel_position = source
                robot.move_vial(DISPENSE_RACK_COORDINATES[source], Locator.vial_carousel)
            if name in ("move_vial_to_carousel", "pipette_into_carousel") and not carousel_open:
                stage = "uncapping the clamped carousel vial"
                robot.goto_safe(Locator.vial_carousel)
                robot.uncap_vial_in_carousel()
                stage = "parking the carousel vial's cap"
                setattr(robot, f"cap_holder_{holder}_free", False)
                robot.goto_safe(holder_positions["approach"])
                robot.cap()
                robot.open_gripper()
                robot.delay(0.5)
                carousel_open = True
            if name == "move_vial_to_carousel":
                continue
            if name == "pipette_into_sonicator":
                destination = SONICATOR_DISPENSE_COORDINATES[target]
                stage = f"transferring source {source} to sonicator {target}"
            else:
                destination = Locator.carousel_dispense
                stage = f"transferring source {source} to the carousel"
            _transfer_source(robot, SOURCE_RACK_COORDINATES[source],
                             SOURCE_ASPIRATION_COORDINATES[source], destination,
                             total, count, interval, Locator.safe_zone)

        if carousel_open:
            stage = "retrieving the carousel vial's cap"
            robot.goto_safe(holder_positions["pickup"])
            robot.close_gripper()
            robot.delay(0.5)
            robot.uncap(pitch=1.35, revs=7)
            stage = "recapping the clamped carousel vial"
            robot.close_clamp()
            robot.goto_safe(Locator.vial_carousel_approach)
            robot.cap()
            robot.open_gripper()
            robot.open_clamp()
            robot.goto_safe(Locator.safe_zone)
            setattr(robot, f"cap_holder_{holder}_free", True)
        robot._formulation_recovery_required = False
    except Exception as error:
        raise RuntimeError(f"Stopped while {stage}: {error}. Check the robot before restarting; no automatic recovery was attempted.") from error


def setup_gui(robot):

    root = tk.Tk()
    app = FormulationEditor(root, robot)
    root.mainloop()