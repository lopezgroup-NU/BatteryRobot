import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os
import time

import tkinter as tk
from tkinter import ttk


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
        root.geometry("600x620")

        self.source_position = tk.StringVar(value="A1")
        self.sonicator_source = tk.StringVar(value="A1")
        self.sonicator_amount = tk.StringVar(value="0")
        self.sonicator_interval = tk.StringVar(value="0")
        self.sonicator_position = tk.StringVar(value="A1")
        self.dispense_position = tk.StringVar(value="A1")
        self.quantity_var = tk.StringVar()
        self.choice_var = tk.StringVar()
        self.mass_var = tk.StringVar()

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

        self.vial_from_carousel = tk.Button(self.action_frame, text="Move Vial\n from Carousel", command=lambda: move_from_carousel_popup())
        self.vial_from_carousel.place(x=120, y=50, width=90, height=70)

        self.pipette_carousel = tk.Button(self.action_frame, text="Pipette into\n Carousel", command=lambda: add_liquid_popup())
        self.pipette_carousel.place(x=20, y=130, width=90, height=70)

        self.arbitrary_move = tk.Button(self.action_frame, text="Pipette into \n Source Vial", command=lambda: pipette_into_source_popup())
        self.arbitrary_move.place(x=120, y=130, width=90, height=70)

        self.pipette_carousel = tk.Button(self.action_frame, text="Sonicate Vial", command=lambda: sonicate_popup())
        self.pipette_carousel.place(x=20, y=210, width=90, height=70)

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

        def sonicate_popup():
            popup = tk.Toplevel(root)
            popup.title("Carousel to Sonicator")
            popup.geometry("560x440")

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

            tk.Button(popup, text="Add", command=self.on_sonicator_button).place(
                x=65, y=385, width=210, height=30)
            tk.Button(popup, text="Close", command=popup.destroy).place(
                x=295, y=385, width=200, height=30)

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

    def on_addButton(self):
        
        loc = self.source_position.get()
        
        from tkinter import messagebox


        # Define the function to trigger the warning
        def show_warning(text):
            messagebox.showwarning("Error", text)
        
        if self.quantity_var.get() == "" and self.mass_var.get() != "" and loc != "": # if a mass was entered but no volume
            mass = int(self.mass_var.get())
            self.list_of_components.append(("pipette_into_carousel", f"s{loc.upper()}", mass, 'm'))
            self.listbox.insert("end", f"{loc.upper()} : {mass}mg")
            self.loc.delete(0, tk.END)
            self.mass_entry.delete(0, tk.END)
        elif self.quantity_var.get() != "" and self.mass_var.get() == "" and loc != "": #vice versa
            quant = int(self.quantity_var.get())
            self.list_of_components.append(("pipette_into_carousel", f"s{loc.upper()}", quant, 'v'))
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

        #self.list_of_components.append(("sonicate_vial", f"d{loc.upper()}", '', ''))
        self.listbox.insert("end", f"{src} -> Sonicator(time={t}, amount={amount})")
        self.loc.delete(0, tk.END)

    def on_tocarousel_button(self):
        
        loc = self.dispense_position.get()

        self.list_of_components.append(("move_vial_to_carousel", f"d{loc.upper()}", '', ''))
        self.listbox.insert("end", f"{loc.upper()} -> Carousel")
        self.loc.delete(0, tk.END)
       
    def on_from_carousel_button(self):
        
        loc = self.dispense_position.get()

        self.list_of_components.append(("move_vial_from_carousel", f"d{loc.upper()}", '', ''))
        self.listbox.insert("end", f"Carousel -> {loc.upper()}")
        self.loc.delete(0, tk.END)

    def on_pipette_into_source_button(self):
            
        loc = self.source_position.get()
        
        from tkinter import messagebox


        # Define the function to trigger the warning
        def show_warning(text):
            messagebox.showwarning("Error", text)
        
        if self.quantity_var.get() != "" and loc != "": # if we get everything needed
            q = int(self.quantity_var.get())
            self.list_of_components.append(("pipette_into_source", f"s{loc.upper()}", q/1000, ''))
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
        

    


    def add_to_list(self, loc = "", quantity = 50, current_list = []):
        current_list.append((loc, quantity))
        return current_list

    
    



def setup_gui(robot):

    root = tk.Tk()
    app = FormulationEditor(root, robot)
    root.mainloop()