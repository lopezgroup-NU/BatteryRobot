import tkinter as tk
from tkinter import filedialog, messagebox
import csv
import os

class SourceRackEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Source Rack Grid Editor")
        self.root.resizable(False, False)
        
        # Fixed dimensions
        self.rows = 8
        self.cols = 6
        
        # Data storage
        self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
        self.filename = "source_rack.csv"
        
        # Main frame
        main_frame = tk.Frame(root, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Grid frame
        self.grid_frame = tk.Frame(main_frame)
        self.grid_frame.pack(pady=10)
        
        # Create grid of entry widgets
        self.entries = []
        for i in range(self.rows):
            row_entries = []
            for j in range(self.cols):
                # Create row and column labels
                if j == 0:
                    row_label = tk.Label(self.grid_frame, text=str(i+1), width=2)
                    row_label.grid(row=i+1, column=0, padx=5)
                
                if i == 0:
                    col_label = tk.Label(self.grid_frame, text=chr(65+j), width=4)
                    col_label.grid(row=0, column=j+1, padx=5)
                
                # Create entry widget
                entry = tk.Entry(self.grid_frame, width=8)
                entry.grid(row=i+1, column=j+1, padx=2, pady=2)
                entry.insert(0, "")
                row_entries.append(entry)
            self.entries.append(row_entries)
        
        # Action buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        # File name entry
        file_frame = tk.Frame(main_frame)
        file_frame.pack(pady=5, fill=tk.X)
        
        tk.Label(file_frame, text="Filename:").pack(side=tk.LEFT, padx=5)
        self.filename_entry = tk.Entry(file_frame, width=20)
        self.filename_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.filename_entry.insert(0, self.filename)
        
        # Load and save buttons
        tk.Button(button_frame, text="Load CSV", command=self.load_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Save CSV", command=self.save_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Clear All", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        
        # Status message
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_label = tk.Label(main_frame, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(side=tk.BOTTOM, fill=tk.X)

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
            with open(filename, 'w', newline='') as file:
                writer = csv.writer(file)
                for row in self.grid_data:
                    writer.writerow(row)
            self.status_var.set(f"Saved to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {str(e)}")
            self.status_var.set("Save failed")

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
                if len(new_data) != self.rows or any(len(row) != self.cols for row in new_data):
                    messagebox.showwarning("Warning", 
                                          f"CSV dimensions don't match grid size (8x6). Data will be truncated or padded.")
                
                # Resize data to fit grid
                self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
                for i in range(min(len(new_data), self.rows)):
                    for j in range(min(len(new_data[i]), self.cols)):
                        self.grid_data[i][j] = new_data[i][j]
                        
                self.update_entry_widgets()
                self.filename_entry.delete(0, tk.END)
                self.filename_entry.insert(0, os.path.basename(filename))
                self.status_var.set(f"Loaded {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {str(e)}")
            self.status_var.set("Load failed")

    def clear_all(self):
        """Clear all entries"""
        for row in self.entries:
            for entry in row:
                entry.delete(0, tk.END)
        self.grid_data = [["" for _ in range(self.cols)] for _ in range(self.rows)]
        self.status_var.set("Grid cleared")

if __name__ == "__main__":
    root = tk.Tk()
    app = SourceRackEditor(root)
    root.mainloop()