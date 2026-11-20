import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import time

import tkinter as tk
from tkinter import ttk

from utils.sonicator import Sonicator, SonicatorError


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

class ToolTip:
    #Small hover tooltip. tkinter has no built-in one
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
        root.title("Formulation Editor")
        root.geometry("700x620")

        self.source_position = tk.StringVar(value="A1")
        self.sonicator_source = tk.StringVar(value="A1")
        self.sonicator_amount = tk.StringVar(value="0")
        self.sonicator_interval = tk.StringVar(value="0")
        self.sonicator_position = tk.StringVar(value="A1")
        self.sonicator_temp = tk.StringVar()
        self.sonicator_minutes = tk.StringVar()
        self.sonicate_text = tk.StringVar(value="Sonicate")
        self.sonicator = Sonicator()
        self.sonicator_busy = False

        self.dispense_position = tk.StringVar(value="A1")
        self.quantity_var = tk.StringVar()
        self.choice_var = tk.StringVar()
        self.mass_var = tk.StringVar()

        self.dropcast_radius = tk.StringVar()
        self.dropcast_volume = tk.StringVar()
        self.dropcast_type = tk.StringVar()

        self.routine_name = tk.StringVar()

        self.heatloc = tk.StringVar()
        self.heat_rack_0_temp = tk.StringVar()
        self.heat_rack_1_temp = tk.StringVar()
        
        # self.chemLabel = tk.Label(root, text="Add Chemical", font=("Helvetica", 11, "bold underline"))
        # self.chemLabel.place(x=350, y=20, width=160, height=30)
        
        
        self.separator1 = ttk.Separator(root, orient="vertical")
        self.separator1.place(x=320, y=10, width=20, height=590)

        self.resetButton = tk.Button(root, text="Reset", command=self.on_resetButton)
        self.resetButton.place(x=140, y=20, width=70, height=30)

        self.dleButton = tk.Button(root, text="Delete Entry", command=self.on_dleButton, font=("Helvetica", 7))
        self.dleButton.place(x=220, y=20, width=70, height=30)

        self.formulateButton = tk.Button(root, text="Formulate", command=self.on_formulateButton, font=("Helvetica", 20, "bold"))
        self.formulateButton.place(x=350, y=500, width=330, height=100)

        

        

        self.compsLabel = tk.Label(root, text="Procedure", font=("Helvetica", 11, "bold underline"))
        self.compsLabel.place(x=10, y=20, width=130, height=30)

        self.action_frame = tk.Frame(root, relief="groove", bd=2)
        self.action_frame.place(x=350, y=20, width=330, height=460)

        self.vial_to_carousel = tk.Button(self.action_frame, text="Move Vial\n to Carousel", command=lambda: move_to_carousel_popup())
        self.vial_to_carousel.place(x=20, y=50, width=90, height=70)

        self.vial_from_carousel = tk.Button(self.action_frame, text="Move Vial\n from Carousel", command=lambda: move_from_carousel_popup())
        self.vial_from_carousel.place(x=120, y=50, width=90, height=70)

        self.pipette_carousel = tk.Button(self.action_frame, text="Pipette into\n Carousel", command=lambda: add_liquid_popup())
        self.pipette_carousel.place(x=20, y=130, width=90, height=70)

        self.arbitrary_move = tk.Button(self.action_frame, text="Pipette into \n Source Vial", command=lambda: pipette_into_source_popup())
        self.arbitrary_move.place(x=120, y=130, width=90, height=70)

        self.pipette_carousel = tk.Button(self.action_frame, text="Sonicate Vial", command=lambda: sonicate_popup())
        self.pipette_carousel.place(x=20, y=210, width=90, height=70)

        self.dropcast = tk.Button(self.action_frame, text="Dropcast", command=lambda: dropcast_popup())
        self.dropcast.place(x=120, y=210, width=90, height=70)

        self.filter = tk.Button(self.action_frame, text="Vacuum \nFilter", command=lambda: filtration_popup())
        self.filter.place(x=20, y=290, width=90, height=70)

        self.error_check = tk.Button(self.action_frame, text="Check for \n Errors", command=lambda: print("nothing here yet"))
        self.error_check.place(x=120, y=290, width=90, height=70)

        self.load_button = tk.Button(self.action_frame, text="Load Routine", command=lambda: load_routine_popup())
        self.load_button.place(x=20, y=370, width=90, height=70)

        self.save_button = tk.Button(self.action_frame, text="Save Routine", command=lambda: save_routine_popup())
        self.save_button.place(x=120, y=370, width=90, height=70)

        self.action_buttons = tk.Label(self.action_frame, text="Insert Action", font=("Helvetica", 13, "bold"))
        self.action_buttons.place(x=10, y=10, width=210, height=30)

        #third column buttons
        self.placeholder0 = tk.Button(self.action_frame, text="Heat Vials", command=lambda: heat_vial_popup())
        self.placeholder0.place(x=220, y=50, width=90, height=70)

        self.placeholder1 = tk.Button(self.action_frame, text="placeholder", command=lambda: print("nothing here yet"))
        self.placeholder1.place(x=220, y=130, width=90, height=70)

        self.placeholder2 = tk.Button(self.action_frame, text="placeholder", command=lambda: print("nothing here yet"))
        self.placeholder2.place(x=220, y=210, width=90, height=70)

        self.placeholder3 = tk.Button(self.action_frame, text="placeholder", command=lambda: print("nothing here yet"))
        self.placeholder3.place(x=220, y=290, width=90, height=70)

        self.placeholder4 = tk.Button(self.action_frame, text="placeholder", command=lambda: print("nothing here yet"))
        self.placeholder4.place(x=220, y=370, width=90, height=70)

        
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
            popup.geometry("500x420")

            xshift = 300
            yshift = 50

            self.loc = tk.Entry(popup, textvariable=self.dispense_position)
            self.loc.place(x=350-xshift, y=70-yshift, width=60, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")

            self.dispense_rack = tk.LabelFrame(popup, text="Dispense Rack", bg="#f6f7fe", relief="groove")
            self.dispense_rack.place(x=350-xshift, y=150-yshift, width=400, height=270)
                        
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

            self.addButton = tk.Button(popup, text="Add", command=self.on_tocarousel_button)
            self.addButton.place(x=350-xshift, y=110-yshift, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=350-xshift, y=380, width=250, height=30)


        def move_from_carousel_popup():
            popup = tk.Toplevel(root)
            popup.title("Move Vial From Carousel")
            popup.geometry("500x420")

            xshift = 300
            yshift = 50

            self.loc = tk.Entry(popup, textvariable=self.dispense_position)
            self.loc.place(x=350-xshift, y=70-yshift, width=60, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")

            self.dispense_rack = tk.LabelFrame(popup, text="Dispense Rack", bg="#f6f7fe", relief="groove")
            self.dispense_rack.place(x=350-xshift, y=150-yshift, width=400, height=270)
                        
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

            self.addButton = tk.Button(popup, text="Add", command=self.on_from_carousel_button)
            self.addButton.place(x=350-xshift, y=110-yshift, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=350-xshift, y=380, width=250, height=30)

        def dropcast_popup():
            popup = tk.Toplevel(root)
            popup.title("Dropcast")
            popup.geometry("420x380")

            xshift = 300
            yshift = 50
            tk.Label(popup, text="Radius(mm)").place(x=50, y=55-yshift, width=100, height=20)
            self.rad = tk.Entry(popup, textvariable=self.dropcast_radius)
            self.rad.place(x=350-xshift, y=70-yshift, width=100, height=30)
            ToolTip(self.rad, "Side length of the square, in millimeters")

            tk.Label(popup, text="Volume(mL)").place(x=160, y=55-yshift, width=100, height=20)
            self.vol = tk.Entry(popup, textvariable=self.dropcast_volume)
            self.vol.place(x=460-xshift, y=70-yshift, width=100, height=30)
            ToolTip(self.vol, "volume in mL, like 0.5")

            tk.Label(popup, text="Location").place(x=270, y=55-yshift, width=100, height=20)
            self.loc = tk.Entry(popup, textvariable=self.heatloc)
            self.loc.place(x=270, y=20, width=100, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")

            self.star_radio = tk.Radiobutton(popup, text="Star", variable=self.dropcast_type, value="1")
            self.star_radio.place(x=600-xshift, y=70, width=80, height=26)

            self.square_radio = tk.Radiobutton(popup, text="Square", variable=self.dropcast_type, value="0")
            self.square_radio.place(x=600-xshift, y=100, width=80, height=26)

            #we are copying the heat rack location picking code here from heat_vial_popup
            self.heat_rack = tk.LabelFrame(popup, text="Heating Rack Dropcast Grid", bg="#f6f7fe", relief="groove")
            self.heat_rack.place(x=50, y=60, width=250, height=200)
                        
            COLS = ["A", "B", "C", "D"]
            ROWS = ["1", "2", "3", "4"]

            for col_idx, col_label in enumerate(COLS):
                header = tk.Label(self.heat_rack, text=col_label, font=("Arial", 10, "bold"))
                header.grid(row=0, column=col_idx + 1, padx=10, pady=5)

            for r_idx, row_label in enumerate(ROWS):

                header = tk.Label(self.heat_rack, text=row_label, font=("Arial", 10, "bold"))
                header.grid(row=r_idx + 1, column=0, padx=10, pady=5)
                
                for c_idx, col_label in enumerate(COLS):
                    # Create the position string
                    pos_value = f"{col_label}{row_label}"
                    
                    # Create the radio button
                    rb = tk.Radiobutton(
                        self.heat_rack, 
                        text=pos_value, 
                        variable=self.heatloc, 
                        value=pos_value
                    )
                    
                    # Place it in the grid window (+1 accounts for headers)
                    rb.grid(row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)

            self.addButton = tk.Button(popup, text="Add", command=self.on_dropcast_button)
            self.addButton.place(x=350-xshift, y=280, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=350-xshift, y=320, width=250, height=30)

        def filtration_popup():
            #TODO add filtration stuff. 
            """
            There should be like sub-popups which let you add washing and extraction steps, respectively. 
            Then once you get everything added in in our non-sub-popup, you should be able to press add 
            and it should send all of the lists and values needed back to the robot to perform actions!
            """
            popup = tk.Toplevel(root)
            popup.title("Vacuum Filter")
            popup.geometry("470x370")

            self.wash_source = tk.StringVar()
            self.wash_amount = tk.StringVar()

            self.wash_vial_list = []
            self.wash_amount_list = []

            self.extract_source = tk.StringVar()
            self.extract_amount = tk.StringVar()

            self.extract_vial_list = []
            self.extract_amount_list = []

            self.wash_list = tk.Listbox(root)
            self.wash_list.insert("end", "Item 1")
            self.wash_list.insert("end", "Item 2")
            self.wash_list.insert("end", "Item 3")
            self.wash_list.place(x=20, y=50, width=130, height=210)

            self.label1 = tk.Label(root, text="Washing Solvents")
            self.label1.place(x=40, y=10, width=90, height=40)

            self.label2 = tk.Label(root, text="Extraction Solvents")
            self.label2.place(x=190, y=10, width=90, height=40)

            self.extract_list = tk.Listbox(root)
            self.extract_list.insert("end", "Item 1")
            self.extract_list.insert("end", "Item 2")
            self.extract_list.insert("end", "Item 3")
            self.extract_list.place(x=170, y=50, width=130, height=210)

            self.add_wash = tk.Button(root, text="Add Washing Step", command=lambda: on_add_wash())
            self.add_wash.place(x=320, y=50, width=130, height=50)

            self.add_extract = tk.Button(root, text="Add Extraction Solvent", command=lambda: on_add_extract())
            self.add_extract.place(x=320, y=110, width=130, height=50)

            self.reset_wash = tk.Button(root, text="Reset", command=lambda: on_reset_wash())
            self.reset_wash.place(x=20, y=270, width=130, height=30)

            self.reset_extract = tk.Button(root, text="Reset", command=lambda: on_reset_extract())
            self.reset_extract.place(x=170, y=270, width=130, height=30)

            self.add_button = tk.Button(root, text="Add to Formulation", command=lambda: on_add_button())
            self.add_button.place(x=320, y=175, width=130, height=110)

            self.close_button = tk.Button(root, text="Close Without Saving", command=lambda: on_close_button())
            self.close_button.place(x=20, y=310, width=280, height=40)

            def on_add_wash(self):
                popup2 = tk.Toplevel(popup)
                popup2.title("Add Washing Step")
                popup2.geometry("420x150")
    
                tk.Label(popup2, text="Vial Location").place(x=50, y=5, width=100, height=20)
                self.rad = tk.Entry(popup2, textvariable=self.wash_source)
                self.rad.place(x=50, y=20, width=100, height=30)
                ToolTip(self.rad, "Side length of the square, in millimeters")
    
                tk.Label(popup2, text="Volume(mL)").place(x=160, y=5, width=100, height=20)
                self.vol = tk.Entry(popup2, textvariable=self.wash_amount)
                self.vol.place(x=160, y=20, width=100, height=30)
                ToolTip(self.vol, "volume in mL, like 0.5")

                self.addButton = tk.Button(popup2, text="Add", command=lambda: print("nothing here yet"))
                self.addButton.place(x=50, y=60, width=250, height=30)
                
                self.close_button = tk.Button(popup2, text="Close", command=popup2.destroy)
                self.close_button.place(x=50, y=100, width=250, height=30)
                pass

            def on_add_extract(self):
                pass

            def on_reset_wash(self):
                pass

            def on_reset_extract(self):
                pass

            def on_add_button(self):
                pass

            def on_close_button(self):
                pass

            


        def save_routine_popup():
            popup = tk.Toplevel(root)
            popup.title("Save Routine")
            popup.geometry("420x150")

            yshift = 50
            tk.Label(popup, text="Enter Routine Name").place(x=50, y=55-yshift, width=250, height=20)
            self.name = tk.Entry(popup, textvariable=self.routine_name)
            self.name.place(x=50, y=70-yshift, width=250, height=30)
            ToolTip(self.name, "Enter the name you would like to save your routine under here!")

            

            self.addButton = tk.Button(popup, text="Save", command=self.on_save_button)
            self.addButton.place(x=50, y=110-yshift, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=50, y=100, width=250, height=30)

        def load_routine_popup():
            

            file_path = filedialog.askopenfilename(
                title="Select a file",
                filetypes=(("Text files", "*.txt"), ("All files", "*.*"))
            )

            # Check if a file was selected (not cancelled)
            if file_path:
                print("Selected file:", file_path)
                with open(file_path, "r") as file:
                    content = file.read()
                    #print(content)
                    self.list_of_components = eval(content)

                    for action in self.list_of_components:
                        self.add_to_listbox(action[4])

            else:
                print("No file selected.")


        def sonicate_popup():
            popup = tk.Toplevel(root)
            popup.title("Carousel to Sonicator")
            popup.geometry("560x505")

            tk.Label(popup, text="Source Rack").place(x=30, y=10, width=110, height=20)
            ttk.Combobox(popup, textvariable=self.sonicator_source,
                         values=[f"{x}{y}" for x in "ABCDEF" for y in range(1, 5)], state="readonly").place(
                             x=30, y=35, width=110, height=30)
            tk.Label(popup, text="Amount (uL)").place(x=165, y=10, width=130, height=20)
            amount_entry = tk.Entry(popup, textvariable=self.sonicator_amount)
            amount_entry.place(x=165, y=35, width=130, height=30)
            ToolTip(amount_entry, "Total volume in uL. A blank amount saves a plan that cannot run yet.")
            tk.Label(popup, text="Interval (seconds)").place(x=320, y=10, width=160, height=20)
            tk.Entry(popup, textvariable=self.sonicator_interval).place(x=320, y=35, width=160, height=30)
            tk.Label(popup, text="Blank interval: one dose. Interval 10: ten doses, 10s after each dose.").place(
                x=20, y=70, width=520, height=20)

            tk.Label(popup, text="Temperature (C)").place(x=30, y=105, width=110, height=20)
            temp_entry = tk.Entry(popup, textvariable=self.sonicator_temp)
            temp_entry.place(x=30, y=130, width=110, height=30)
            ToolTip(temp_entry, "Whole degrees C; blank leaves the heater off")
            tk.Label(popup, text="Sonication time (min)").place(x=165, y=105, width=150, height=20)
            tk.Entry(popup, textvariable=self.sonicator_minutes).place(x=165, y=130, width=130, height=30)
            tk.Button(popup, textvariable=self.sonicate_text, command=self.on_sonicate_button).place(
                x=320, y=130, width=160, height=30)

            rack = tk.LabelFrame(popup, text="Sonicator", relief="groove")
            rack.place(x=65, y=170, width=430, height=265)
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

            tk.Button(popup, text="Add", command=self.on_sonicator_button).place(
                x=65, y=450, width=210, height=30)
            tk.Button(popup, text="Close", command=popup.destroy).place(
                x=295, y=450, width=200, height=30)

        def resposition_popup():
            popup = tk.Toplevel(root)
            popup.title("Reposition Vial")
            popup.geometry("1000x500")
        
        def add_liquid_popup():
            popup = tk.Toplevel(root)
            popup.title("Pipette Liquid into Carousel")
            popup.geometry("420x420")
            xshift = 300
            yshift = 50

            self.loc = tk.Entry(popup, textvariable=self.source_position)
            self.loc.place(x=350-xshift, y=70-yshift, width=60, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")
    
            self.locLabel = tk.Label(popup, text="Location", font=("Helvetica", 7))
            self.locLabel.place(x=350-xshift, y=50-yshift, width=60, height=20)
    
            self.quantLabel = tk.Label(popup, text="Quantity", font=("Helvetica", 7))
            self.quantLabel.place(x=435-xshift, y=50-yshift, width=60, height=20)
    
            self.quantity = tk.Entry(popup, textvariable=self.quantity_var)
            self.quantity.place(x=420-xshift, y=70-yshift, width=90, height=30)
            ToolTip(self.quantity, "Integer quantity in microliters; like \"500\"")

            self.mass_entry = tk.Entry(popup, textvariable=self.mass_var)
            self.mass_entry.place(x=520-xshift, y=70-yshift, width=80, height=30)
            ToolTip(self.mass_entry, "Integer mass in mg")
            
            #self.dispense_rack = tk.LabelFrame(popup, text="Dispense Rack", bg="#f6f7fe", relief="groove")
            #self.dispense_rack.place(x=350-xshift, y=150-yshift, width=400, height=270)

            self.source_rack = tk.LabelFrame(popup, text="Source Rack", bg="#f6f7fe", relief="groove")
            self.source_rack.place(x=350-xshift, y=150-yshift, width=350, height=270)

            self.label9 = tk.Label(popup, text="Volume", font=("Helvetica", 7, "bold"))
            self.label9.place(x=445-xshift, y=50-yshift, width=60, height=20)
    
            self.label10 = tk.Label(popup, text="Mass", font=("Helvetica", 7, "bold"))
            self.label10.place(x=530-xshift, y=50-yshift, width=60, height=20)

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

            self.addButton = tk.Button(popup, text="Add", command=self.on_addButton)
            self.addButton.place(x=350-xshift, y=110-yshift, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=350-xshift, y=380, width=250, height=30)
            #close_button.pack(pady=10)
        
        def pipette_into_source_popup():
            popup = tk.Toplevel(root)
            popup.title("Pipette Liquid from Carousel into Source")
            popup.geometry("420x420")
            xshift = 300
            yshift = 50

            self.loc = tk.Entry(popup, textvariable=self.source_position)
            self.loc.place(x=350-xshift, y=70-yshift, width=60, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")
    
            self.locLabel = tk.Label(popup, text="Location", font=("Helvetica", 7))
            self.locLabel.place(x=350-xshift, y=50-yshift, width=60, height=20)
    
            self.quantLabel = tk.Label(popup, text="Quantity", font=("Helvetica", 7))
            self.quantLabel.place(x=435-xshift, y=50-yshift, width=60, height=20)
    
            self.quantity = tk.Entry(popup, textvariable=self.quantity_var)
            self.quantity.place(x=420-xshift, y=70-yshift, width=90, height=30)
            ToolTip(self.quantity, "Integer quantity in microliters; like \"500\"")

            

            self.source_rack = tk.LabelFrame(popup, text="Source Rack", bg="#f6f7fe", relief="groove")
            self.source_rack.place(x=350-xshift, y=150-yshift, width=350, height=270)

            self.label9 = tk.Label(popup, text="Volume", font=("Helvetica", 7, "bold"))
            self.label9.place(x=445-xshift, y=50-yshift, width=60, height=20)
    
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
            

            self.addButton = tk.Button(popup, text="Add", command=self.on_pipette_into_source_button)
            self.addButton.place(x=350-xshift, y=110-yshift, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=350-xshift, y=380, width=250, height=30)
            #close_button.pack(pady=10)

        def heat_vial_popup():
            popup = tk.Toplevel(root)
            popup.title("Heat vial")
            popup.geometry("1000x420")

            self.heat_rack_0_label = tk.Label(popup, text="Upper Rack Temp.", font=("Arial", 10))
            self.heat_rack_0_label.place(x=780, y=100, width=130, height=30)
            self.heat_rack_0_entry = tk.Entry(popup, textvariable=self.heat_rack_0_temp)
            self.heat_rack_0_entry.place(x=780, y=130, width=100, height=30)
            ToolTip(self.heat_rack_0_entry, "Temperature in degrees Celsius, like 60")

            self.heat_rack_1_label = tk.Label(popup, text="Lower Rack Temp.", font=("Arial", 10))
            self.heat_rack_1_label.place(x=780, y=220, width=130, height=30)
            self.heat_rack_1_entry = tk.Entry(popup, textvariable=self.heat_rack_1_temp)
            self.heat_rack_1_entry.place(x=780, y=250, width=100, height=30)
            ToolTip(self.heat_rack_1_entry, "Temperature in degrees Celsius, like 60")

            self.loc = tk.Entry(popup, textvariable=self.dispense_position)
            self.loc.place(x=50, y=20, width=60, height=30)
            ToolTip(self.loc, "Location; like \"A1\"")

            self.dispense_rack = tk.LabelFrame(popup, text="Dispense Rack", bg="#f6f7fe", relief="groove")
            self.dispense_rack.place(x=50, y=100, width=460, height=270)
                        
            COLS = ["A", "B", "C", "D", "E", "F", "G"] #there is technically supposed to be an H here but it's unindexable rn #TODO
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

            rbc = tk.Radiobutton(
                self.dispense_rack, 
                text="CAROUSEL", 
                variable=self.dispense_position, 
                value="CAROUSEL"
            )
            rbc.grid(row=1, column=6, padx=5, pady=5)

            self.heatloc_entry = tk.Entry(popup, textvariable=self.heatloc)
            self.heatloc_entry.place(x=520, y=20, width=60, height=30)
            ToolTip(self.heatloc_entry, "Location; like \"A1\"")

            self.heat_rack = tk.LabelFrame(popup, text="Heating Racks", bg="#f6f7fe", relief="groove")
            self.heat_rack.place(x=520, y=100, width=250, height=270)
                        
            COLS = ["A", "B", "C", "D"]
            ROWS = ["1", "2", "3", "4", "5", "6"]

            for col_idx, col_label in enumerate(COLS):
                header = tk.Label(self.heat_rack, text=col_label, font=("Arial", 10, "bold"))
                header.grid(row=0, column=col_idx + 1, padx=10, pady=5)

            for r_idx, row_label in enumerate(ROWS):

                header = tk.Label(self.heat_rack, text=row_label, font=("Arial", 10, "bold"))
                header.grid(row=r_idx + 1, column=0, padx=10, pady=5)
                
                for c_idx, col_label in enumerate(COLS):
                    # Create the position string
                    pos_value = f"{col_label}{row_label}"
                    
                    # Create the radio button
                    rb = tk.Radiobutton(
                        self.heat_rack, 
                        text=pos_value, 
                        variable=self.heatloc, 
                        value=pos_value
                    )
                    
                    # Place it in the grid window (+1 accounts for headers)
                    rb.grid(row=r_idx + 1, column=c_idx + 1, padx=5, pady=5)

            self.separator1 = ttk.Separator(self.heat_rack, orient="horizontal")
            self.separator1.place(x=20, y=132, width=210, height=5)

            self.addButton = tk.Button(popup, text="Add", command=self.on_heat_vial)
            self.addButton.place(x=50, y=60, width=250, height=30)
            
            self.close_button = tk.Button(popup, text="Close", command=popup.destroy)
            self.close_button.place(x=50, y=380, width=250, height=30)


        self.listbox = tk.Listbox(root)
        
        self.listbox.place(x=20, y=60, width=270, height=550)

        
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

    def on_heat_vial(self):

        grab_loc = self.dispense_position.get()
        heat_loc = self.heatloc.get()
        rack0temp = float(self.heat_rack_0_temp.get())
        rack1temp = float(self.heat_rack_1_temp.get())


        if grab_loc == "CAROUSEL":
            self.list_of_components.append(("heat_vial", "carousel", f"{heat_loc.upper()}", [rack0temp, rack1temp], f"Carousel -> Heat Rack {heat_loc.upper()}; H0@ {rack0temp}C, H1@ {rack1temp}C"))
            self.listbox.insert("end", f"Carousel -> Heat Rack {heat_loc.upper()}; H0@ {rack0temp}C, H1@ {rack1temp}C")
            self.loc.delete(0, tk.END)
            self.heatloc_entry.delete(0, tk.END)
            self.heat_rack_0_entry.delete(0, tk.END)
            self.heat_rack_1_entry.delete(0, tk.END)
        else:
            self.list_of_components.append(("heat_vial", f"d{grab_loc.upper()}", f"{heat_loc.upper()}", [rack0temp, rack1temp],f"Carousel -> Heat Rack {heat_loc.upper()}; H0@ {rack0temp}C, H1@ {rack1temp}C"))
            self.listbox.insert("end", f"Carousel -> Heat Rack {heat_loc.upper()}; H0@ {rack0temp}C, H1@ {rack1temp}C")
            self.loc.delete(0, tk.END)
            self.heatloc_entry.delete(0, tk.END)
            self.heat_rack_0_entry.delete(0, tk.END)
            self.heat_rack_1_entry.delete(0, tk.END)
        pass

    def on_addButton(self):
        
        loc = self.source_position.get()
        
        from tkinter import messagebox


        # Define the function to trigger the warning
        def show_warning(text):
            messagebox.showwarning("Error", text)
        
        if self.quantity_var.get() == "" and self.mass_var.get() != "" and loc != "": # if a mass was entered but no volume
            mass = int(self.mass_var.get())
            self.list_of_components.append(("pipette_into_carousel", f"s{loc.upper()}", mass, 'm', f"{loc.upper()} : {mass}mg"))
            self.listbox.insert("end", f"{loc.upper()} : {mass}mg")
            self.loc.delete(0, tk.END)
            self.mass_entry.delete(0, tk.END)
        elif self.quantity_var.get() != "" and self.mass_var.get() == "" and loc != "": #vice versa
            quant = int(self.quantity_var.get())
            self.list_of_components.append(("pipette_into_carousel", f"s{loc.upper()}", quant, 'v', f"{loc.upper()} : {quant}uL"))
            self.listbox.insert("end", f"{loc.upper()} : {quant}uL")
            self.loc.delete(0, tk.END)
            self.quantity.delete(0, tk.END)
        elif loc == "":
             show_warning("No location selected!")
        elif self.quantity_var.get() == "" and self.mass_var.get() == "":
                     show_warning("No mass or volume entered!")
        elif self.quantity_var.get() != "" and self.mass_var.get() != "":
                             show_warning("Both mass and volume entered; only one can be chosen!")

    def on_sonicator_button(self):
            
        src = self.sonicator_source.get()
        t = self.sonicator_interval.get()
        amount = self.sonicator_amount.get()
        sonic_loc = self.sonicator_position.get()

        self.list_of_components.append(("sonicate_vial", f"d{sonic_loc.upper()}", '', '', f"{src} -> Sonicator(time={t}, amount={amount})"))
        self.listbox.insert("end", f"{src} -> Sonicator(time={t}, amount={amount})")
        # self.loc.delete(0, tk.END)

    def on_sonicate_button(self):
        if self.sonicator_busy:
            self.sonicator.stop()
            return
        try:
            self.sonicator.start(self.sonicator_minutes.get(), self.sonicator_temp.get())
        except SonicatorError as exc:
            messagebox.showerror("Sonicator", str(exc))
            return
        self.sonicator_busy = True
        self.update_sonicator_status()

    def update_sonicator_status(self):
        snap = self.sonicator.snapshot()
        if snap["running"]:
            minutes, seconds = divmod(int(snap["remaining_s"]), 60)
            self.sonicate_text.set(f"Stop  {minutes:02d}:{seconds:02d}")
            self.root.after(200, self.update_sonicator_status)
            return
        self.sonicator_busy = False
        self.sonicate_text.set("Sonicate")
        if snap["error"]:
            messagebox.showerror("Sonicator", f"{snap['error']}\n\nCheck the sonicator by hand.")

    def on_tocarousel_button(self):
        
        loc = self.dispense_position.get()

        self.list_of_components.append(("move_vial_to_carousel", f"d{loc.upper()}", '', '', f"{loc.upper()} -> Carousel"))
        self.listbox.insert("end", f"{loc.upper()} -> Carousel")
        self.loc.delete(0, tk.END)
       
    def on_from_carousel_button(self):
        
        loc = self.dispense_position.get()

        self.list_of_components.append(("move_vial_from_carousel", f"d{loc.upper()}", '', '', f"Carousel -> {loc.upper()}"))
        self.listbox.insert("end", f"Carousel -> {loc.upper()}")
        self.loc.delete(0, tk.END)

    def on_filtration_button(self):
        rad = float(self.dropcast_radius.get())
        vol = float(self.dropcast_volume.get())
        drop_type = int(self.dropcast_type.get())
        if drop_type == 0:
            self.list_of_components.append(("sqdropcast",'', rad, vol, f"Square dropcast: r={rad}, v={vol}"))
            self.listbox.insert("end", f"Square dropcast: r={rad}, v={vol}")
        if drop_type == 1:
                self.list_of_components.append(("stdropcast",'', rad, vol, f"Star dropcast: r={rad}, v={vol}"))
                self.listbox.insert("end", f"Star dropcast: r={rad}, v={vol}")
        self.rad.delete(0, tk.END)
        self.vol.delete(0, tk.END)

    def on_dropcast_button(self):
        loc = self.heatloc.get()
        rad = float(self.dropcast_radius.get())
        vol = float(self.dropcast_volume.get())
        drop_type = int(self.dropcast_type.get())
        if drop_type == 0:
            self.list_of_components.append(("sqdropcast",loc, rad, vol, f"Square dropcast: r={rad}, v={vol}"))
            self.listbox.insert("end", f"Square dropcast: r={rad}, v={vol}")
        if drop_type == 1:
                self.list_of_components.append(("stdropcast",loc, rad, vol, f"Star dropcast: r={rad}, v={vol}"))
                self.listbox.insert("end", f"Star dropcast: r={rad}, v={vol}")
        self.rad.delete(0, tk.END)
        self.vol.delete(0, tk.END)
        self.loc.delete(0, tk.END)
        

    def on_save_button(self):
        from pathlib import Path

        name = str(self.routine_name.get())
        routine_text = str(self.list_of_components)


        file_path = Path("saved_formulation_routines") / f"{name}.txt"

        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(routine_text, encoding="utf-8")
        

        self.name.delete(0, tk.END)

    def on_pipette_into_source_button(self):
            
        loc = self.source_position.get()
        
        from tkinter import messagebox


        # Define the function to trigger the warning
        def show_warning(text):
            messagebox.showwarning("Error", text)
        
        if self.quantity_var.get() != "" and loc != "": # if we get everything needed
            q = int(self.quantity_var.get())
            self.list_of_components.append(("pipette_into_source", f"s{loc.upper()}", q/1000, '', f"pipette {q} uL into source rack {loc}"))
            self.listbox.insert("end", f"pipette {q} uL into source rack {loc}")
            self.loc.delete(0, tk.END)
            self.quantity.delete(0, tk.END)

    def on_resetButton(self):
        self.listbox.delete(0, tk.END)
        self.list_of_components = []
        pass

    def on_dleButton(self):
        self.listbox.delete(self.listbox.curselection()[0])
        
        pass

    def on_formulateButton(self):
        self.robot.formulate_in_order(self.list_of_components)

    def add_to_listbox(self, txt):
        self.listbox.insert("end", txt)
        

    
    



def setup_gui(robot):

    root = tk.Tk()
    app = FormulationEditor(root, robot)
    root.mainloop()