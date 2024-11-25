class DispRack():
    """
    mapping solutions to indexes of rack_disp_official 

    vial indexing is as follows. The entire rack is a 6x8 grid. 
    
    Rows are labelled 1-6, columns are labelled A-H
    
    DispRack slots:              DispRack (v means vial, x means robot can't reach position):
    
    H1 G1 F1 E1 D1 C1 B1 A1      v v v v v v x v 
    H2 G2 F2 E2 D2 C2 B2 A2      v v v v v v v v 
    H3 G3 F3 E3 D3 C3 B3 A3  --> v v v v v v v v
    H4 G4 F4 E4 D4 C4 B4 A4      v v v v v v v v
    H5 G5 F5 E5 D5 C5 B5 A5      v v v v v v v v
    H6 G6 F6 E6 D6 C6 B6 A6      v v v v v v v v
        
    Numerical mapping of DispRack:
    
    42 36 30 24 18 12 x  0 
    43 37 31 25 19 13 7  1 
    44 38 32 26 20 14 8  2 
    45 39 33 27 21 15 9  3 
    46 40 34 28 22 16 10 4 
    47 41 35 29 23 17 11 5 

    """
    
    def __init__(self, vials, vols, concs, csv_path):
        #no duplicates
        if len(vials) != len(set(vials)):
            raise Exception("No duplicates!")
        
        for i in range(len(vials)):
            #map vial name to index
            if vials[i] != "n" or vials[i] != "x":
                setattr(self, vials[i], i)

                #map vial volumes
                setattr(self, vials[i] + "_vol", int(vols[i]))

                #map vial concentrations
                setattr(self, vials[i] + "_conc", int(concs[i]))

                #map grid to vial name. convert index to grid, then match to vial name 
                setattr(self, self.index_to_grid(i), vials[i])

        self.csv_path = csv_path

    def index_to_grid(self, index):
        """
        Given index (0 to 47) returns grid position (A1 - H6)
        """
        if index < 0 or index > 47:
            raise Exception("DispRack: Enter valid grid index!")

        cols = ["A", "B", "C", "D", "E", "F", "G", "H"]
        return cols[index//6] + str(index % 6 + 1)
    
    def grid_to_index(self, coordinate):
        """
        Given grid position (A1 - H6) return index (0 to 47)
        """
        if coordinate[0] not in ["A", "B", "C", "D", "E", "F", "G", "H"] or coordinate[1] not in ["1", "2", "3", "4", "5", "6", "7", "8"]:
            print("Enter valid coordinates!")
            return -1 

        mapping = {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
            "E": 4,
            "F": 5,
            "G": 6,
            "H": 7,
        }
        return mapping[coordinate[0]] * 6 + int(coordinate[1]) - 1