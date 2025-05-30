import pandas as pd
from utils.ExceptionUtils import *
from pathlib import Path

class HeatRack():
    """
    mapping solutions to indexes of a single heatplate

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

    @classmethod
    def index_to_pos(self, index):
        """
        Given index (0 to 23) returns position (A1 - D3) followed by plate number
        e.g. A1-1, A1-2 
        """
        if index < 0 or index > 23:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid grid index!")

        racknum = str(index // 12 + 1)

        cols = ["A", "B", "C", "D"]
        return cols[index//3] + str(index % 3 + 1) + "-" + racknum 
    
    @classmethod
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
        return mapping[pos[0]] * 3 + int(pos[1]) - 1, int(pos[-1])
    
    def get_free(self):
        """
        Return next free slot on heatrack and mark that as taken.
        """

# implement this if/when you want to manage the heatplates together as one
# class DualHeatRack:
#     """
#     We need to manage the two heatplates as a single logical unit.
#     """
#     def __init__(self, csv_path_rack1, csv_path_rack2):
#         self.rack1 = HeatRack(csv_path_rack1)
#         self.rack2 = HeatRack(csv_path_rack2)
#         self.name = "DualHeatRack"  

#     def index_to_pos(self, index):
#         """Convert global index (0–23) to position (A1–D3 for rack1, E1–H3 for rack2)."""
#         if 0 <= index <= 11:
#             return self.rack1.index_to_pos(index)
#         elif 12 <= index <= 23:
#             return chr(ord("E") + (index - 12) // 3) + str((index - 12) % 3 + 1)
#         else:
#             raise ContinuableRuntimeError(f"{self.name}: Index {index} out of range (0–23)!")
    
#     def pos_to_index(self, pos):
#         """Convert position (A1–H3) to global index (0–23)."""
#         if pos[0] in ["A", "B", "C", "D"]:
#             return self.rack1.pos_to_index(pos)
#         elif pos[0] in ["E", "F", "G", "H"]:
#             return 12 + (ord(pos[0]) - ord("E")) * 3 + int(pos[1]) - 1
#         else:
#             raise ContinuableRuntimeError(f"{self.name}: Invalid position {pos}!") 
