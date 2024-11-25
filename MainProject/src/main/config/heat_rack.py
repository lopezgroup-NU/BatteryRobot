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
    
    def __init__(self, csv_path):
        self.csv_path = csv_path

    def index_to_grid(self, index):
        """
        Given index (0 to 11) returns grid position (A1 - D3)
        """
        if index < 0 or index > 11:
            print("Enter valid index!")
            return 

        cols = ["D", "C", "B", "A"]
        return cols[index//3] + str(index % 3 + 1)
    
    def grid_to_index(self, coordinate):
        """
        Given grid position (A1 - D3) return index (0 to 11)
        """
        if coordinate[0] not in ["D", "C", "B", "A"] or coordinate[1] not in ["1", "2", "3"]:
            print("Enter valid coordinates!")
            return -1 

        mapping = {
            "D": 0,
            "C": 1,
            "B": 2,
            "A": 3,
        }
        return mapping[coordinate[0]] * 3 + int(coordinate[1]) - 1