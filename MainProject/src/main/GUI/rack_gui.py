import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os

class RackEditor:
    """Base class for rack editors with common functionality"""
    
    def __init__(self, root, filename, source_rack_filename=None, rows=None, cols=None, title="Rack Grid Editor", parent=None):
        self.root = root
        self.parent = parent
        self.root.title(title)
        self.root.resizable(False, False)
        self.rows = rows
        self.cols = cols
        self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
        self.filename = filename
        self.source_rack_filename = source_rack_filename
        
        self.main_frame = tk.Frame(root, padx=10, pady=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.grid_frame = tk.Frame(self.main_frame)
        self.grid_frame.pack(pady=10)
        
        self.entries = []
        for i in range(self.rows):
            row_entries = []
            for j in range(self.cols):
                if j == 0:
                    row_label = tk.Label(self.grid_frame, text=str(i+1), width=2)
                    row_label.grid(row=i+1, column=0, padx=5)
                
                if i == 0:
                    col_label = tk.Label(self.grid_frame, text=chr(65 + (self.cols - 1 - j)), width=4)
                    col_label.grid(row=0, column=j+1, padx=5)
                
                entry = tk.Entry(self.grid_frame, width=8)
                entry.grid(row=i+1, column=j+1, padx=2, pady=2)
                entry.insert(0, "")
                row_entries.append(entry)
            self.entries.append(row_entries)
        
        button_frame = tk.Frame(self.main_frame)
        button_frame.pack(pady=10)
        
        file_frame = tk.Frame(self.main_frame)
        file_frame.pack(pady=5, fill=tk.X)
        
        tk.Label(file_frame, text="Filename:").pack(side=tk.LEFT, padx=5)
        self.filename_entry = tk.Entry(file_frame, width=20)
        self.filename_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.filename_entry.insert(0, self.filename)
        
        tk.Button(button_frame, text="Load CSV", command=self.load_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Save CSV", command=self.save_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_label = tk.Label(self.main_frame, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.load_default_csv()

    def load_default_csv(self):
        """Load the default CSV file at startup"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', newline='') as file:
                    reader = csv.reader(file)
                    new_data = list(reader)
                    
                    # Resize data to fit grid
                    self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
                    for i in range(min(len(new_data), self.rows)):
                        for j in range(min(len(new_data[i]) if i < len(new_data) else 0, self.cols)):
                            self.grid_data[i][j] = new_data[i][j]
                            
                    self.update_entry_widgets()
                    self.status_var.set(f"Loaded default file: {self.filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load default file: {str(e)}")
                self.status_var.set("Default load failed")
        else:
            self.status_var.set(f"Default file '{self.filename}' not found. Starting with empty grid.")

    def update_grid_data(self):
        """Update internal grid data from entry widgets"""
        for i in range(self.rows):
            for j in range(self.cols):
                self.grid_data[i][j] = self.entries[i][j].get()

    def update_entry_widgets(self):
        """Update entry widgets from internal grid data"""
        for i in range(self.rows):
            for j in range(self.cols):
                self.entries[i][j].delete(0, tk.END)
                self.entries[i][j].insert(0, self.grid_data[i][j])

    def save_csv(self):
        """Save grid data to CSV file"""
        self.update_grid_data()
        filename = self.filename_entry.get()
        
        if not filename.endswith('.csv'):
            filename += '.csv'
        
        try:
            # Ensure directory exists
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
                
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                for row in self.grid_data:
                    writer.writerow(row)
            self.status_var.set(f"Saved to {filename}")
            return True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")
            self.status_var.set("Save failed")
            return False

    def load_csv(self):
        """Load grid data from CSV file"""
        filename = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            with open(filename, 'r', newline='') as file:
                reader = csv.reader(file)
                new_data = list(reader)
                
                # Validate dimensions
                if len(new_data) != self.rows or any(len(row) != self.cols for row in new_data if row):
                    messagebox.showwarning("Warning", 
                                          f"CSV dimensions don't match grid size ({self.rows}x{self.cols}). Data will be truncated or padded.")
                
                # Resize data to fit grid
                self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
                for i in range(min(len(new_data), self.rows)):
                    for j in range(min(len(new_data[i]) if i < len(new_data) else 0, self.cols)):
                        self.grid_data[i][j] = new_data[i][j]
                        
                self.update_entry_widgets()
                self.filename_entry.delete(0, tk.END)
                self.filename_entry.insert(0, filename)  # Use full path
                self.status_var.set(f"Loaded {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")
            self.status_var.set("Load failed")

    def clear_all(self):
        """Clear all entries - keep 'x' values and make others 'e'"""
        self.update_grid_data()  # Make sure grid_data is current
        
        for i in range(self.rows):
            for j in range(self.cols):
                current_value = self.grid_data[i][j]
                self.entries[i][j].delete(0, tk.END)
                
                # Keep 'x' values, make others 'e'
                if current_value == "x":
                    self.entries[i][j].insert(0, "x")
                    self.grid_data[i][j] = "x"
                else:
                    self.entries[i][j].insert(0, "e")
                    self.grid_data[i][j] = "e"
        
        self.status_var.set("Grid cleared - 'x' values preserved, others filled with 'e'")
    
    def close(self):
        """Close this editor window"""
        self.root.destroy()


class DispRackEditor(RackEditor):
    """Editor for the Disp Rack (6x8)"""
    
    def __init__(self, root, filename="config/disp_rack.csv", source_rack_filename="config/source_rack.csv", parent=None):
        super().__init__(root, filename, source_rack_filename=source_rack_filename, rows=6, cols=8, title="Disp Rack Grid Editor", parent=parent)
        
        # Add next button to save and proceed to source rack
        self.next_button = tk.Button(self.main_frame, text="Next: Source Rack Editor →", 
                                    command=self.proceed_to_source_rack,
                                    bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                                    padx=15, pady=5)
        self.next_button.pack(pady=10)
    
    def proceed_to_source_rack(self):
        """Save the current grid, close this window, and open the Source Rack Editor"""
        # First save the current grid data
        if self.save_csv():
            # Create a new window for source rack
            source_window = tk.Tk()
            source_editor = SourceRackEditor(source_window, self.source_rack_filename, parent=self)
            
            # Close this window
            self.close()


class SourceRackEditor(RackEditor):
    """Editor for the Source Rack (6x5)"""
    
    def __init__(self, root, filename="config/source_rack.csv", parent=None):
        super().__init__(root, filename, source_rack_filename=None, rows=6, cols=5, title="Source Rack Grid Editor", parent=parent)
        
        # Add optional Back button to return to Disp Rack
        if parent:
            self.back_button = tk.Button(self.main_frame, text="← Back to Disp Rack", 
                                       command=self.back_to_disp_rack)
            self.back_button.pack(pady=5)
    
    def back_to_disp_rack(self):
        """Save the current grid, close this window, and return to Disp Rack"""
        if self.save_csv():
            disp_window = tk.Tk()
            disp_editor = DispRackEditor(disp_window, "config/disp_rack.csv")
            
            self.close()

def setup_gui():
    root = tk.Tk()
    source_rack_filename = "config/source_rack.csv"
    app = DispRackEditor(root, filename=disp_rack_filename, source_rack_filename=source_rack_filename)
    root.mainloop()
    
if __name__ == "__main__":
    root = tk.Tk()
    disp_rack_filename = "config/disp_rack.csv"
    source_rack_filename = "config/source_rack.csv"
    app = DispRackEditor(root, filename=disp_rack_filename, source_rack_filename=source_rack_filename)
    root.mainloop()