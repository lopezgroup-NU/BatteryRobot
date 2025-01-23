import pandas as pd
from utils.ExceptionUtils import *
from pathlib import Path

class HeatRack():
    """
    mapping solutions to indexes of heatplate_official

    vial indexing is as follows. The entire rack is a 3x4 grid. 
    
    Rows are labelled 1-3, columns are labelled A-D
    
    HeatRack slots:               HeatRack 
    
    A1 B1 C1 D1      v v v v  
    A2 B2 C2 D2  --> v v v v  
    A3 B3 C3 D3      v v v v      
    
    Numerical mapping of HeatRack:
    
    9  6 3 0
    10 7 4 1
    11 8 5 2
    """
    rack_max_index = 11
    name = "HeatRack"
    
    def __init__(self, csv_path):
        df = pd.read_csv(csv_path, header=None)
        self.heat_rack_df = df
        self.path = Path(csv_path).with_suffix("")

    def index_to_pos(self, index):
        """
        Given index (0 to 11) returns position (A1 - D3)
        """
        if index < 0 or index > 11:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid grid index!")


        cols = ["A", "B", "C", "D"]
        return cols[index//3] + str(index % 3 + 1)
    
    def pos_to_index(self, pos):
        """
        Given position (A1 - D3) return index (0 to 11)
        """
        if pos[0] not in ["A", "B", "C", "D"] or pos[1] not in ["1", "2", "3"]:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid position!")

        mapping = {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
        }
        return mapping[pos[0]] * 3 + int(pos[1]) - 1