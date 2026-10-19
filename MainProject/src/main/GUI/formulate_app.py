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

        self.action_frame = tk.Frame(root, relief="groove", bd=2)
        self.action_frame.place(x=260, y=20, width=230, height=270)

        self.vial_to_carousel = tk.Button(self.action_frame, text="Move Vial to Carousel", command=self.on_vial_to_carousel)
        self.vial_to_carousel.place(x=20, y=50, width=90, height=70)

        self.vial_from_carousel = tk.Button(self.action_frame, text="Move Vial from Carousel", command=self.on_vial_from_carousel)
        self.vial_from_carousel.place(x=120, y=50, width=90, height=70)

        self.pipette_carousel = tk.Button(self.action_frame, text="Pipette into Carousel", command=self.on_pipette_carousel)
        self.pipette_carousel.place(x=20, y=130, width=90, height=70)

        self.arbitrary_move = tk.Button(self.action_frame, text="Reposition Vial", command=lambda: open_popup())
        self.arbitrary_move.place(x=120, y=130, width=90, height=70)

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

        def open_popup():
            popup = tk.Toplevel(root)
            popup.title("Popup Window")
            popup.geometry("600x500")

            label = tk.Label(popup, text="Hello! This is a popup window.")
            label.pack(pady=20)

            self.dispense_rack = tk.LabelFrame(popup, text="Dispense Rack", bg="#f6f7fe", relief="groove")
            self.dispense_rack.place(x=350, y=150, width=400, height=270)

            self.source_rack = tk.LabelFrame(popup, text="Source Rack", bg="#f6f7fe", relief="groove")
            self.source_rack.place(x=760, y=150, width=350, height=270)


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

            close_button = tk.Button(popup, text="Close", command=popup.destroy)
            close_button.pack(pady=10)
        
        self.listbox = tk.Listbox(root)
        
        self.listbox.place(x=20, y=60, width=270, height=550)

        
        self.up_button = tk.Button(root, text="^", command=lambda: move(self.listbox, -1), font=("Helvetica", 13))
        self.up_button.place(x=295, y=60, width=20, height=30)

        self.dn_button = tk.Button(root, text="v", command=lambda: move(self.listbox, 1))
        self.dn_button.place(x=295, y=95, width=20, height=30)

        

    def on_vial_to_carousel(self):
        self.open_popup()
    
    def on_vial_from_carousel(self):
        pass

    def on_pipette_carousel(self):
        pass

    def on_arbitrary_move(self):
        pass

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
        elif self.quantity_var.get() != "" and self.mass_var.get() != "":
                             show_warning("Both mass and volume entered; only one can be chosen!")

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