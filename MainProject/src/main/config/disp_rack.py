import pandas as pd
from utils.ExceptionUtils import *
class DispRack():
    """
    mapping solutions to indexes of rack_disp_official.

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

    Naming conventions:

    - <vial_name> <vial_vol> <vial_concentration> for non-empty vial
    - 'purge' if vial is to be used for purging (robot assumes vial is full (8ml))
    - 'e' for empty vial
    - 'n' for no vial

    """
    name = "DispRack"
    rack_max_index = 47
    purge_sources = []

    def __init__(self, csv_path):
        #no duplicates
        df = pd.read_csv(csv_path, header=None)
        self.disp_rack_df = df
        self.csv_path_updated = csv_path + "_updated" #when rack state is updated, store df here

        self.invalid_index = set()
        vials = set()

        i = 0 #track index
        df = df.iloc[:, ::-1]
        for col in df:
            for el in df[col]:
                if i > self.rack_max_index:
                    raise InitializationError(f"{self.name}: Too many indexes, fix rack csv file.")

                if el == 'x': # x means robot cannot reach position. 
                    self.invalid_index.add(i)
                elif el == 'e' or el == 'n': # n means no vial at given index. 
                    pass
                elif el.strip() == "purge":
                    #store each purge source as array [volume, index, pos]
                    self.purge_sources.append([8, i, self.index_to_pos(i)])
                else: 
                    if len(el.split()) != 3:
                        print(el)
                        raise InitializationError(f"{self.name}: Each vial with contents must have 3 items: vial_name, volume, and concentration")       

                    vial, vol, conc = el.split()

                    if vial in vials:
                        raise InitializationError(f"{self.name}: No duplicate vial names!")

                    #map vial to index
                    setattr(self, vial + "_id", i)

                    #map vial volumes
                    setattr(self, vial + "_vol", float(vol))

                    #map vial concentrations
                    setattr(self, vial + "_conc", float(conc))

                    try:
                        #map grid to vial name. convert index to grid, then match to vial name 
                        setattr(self, self.index_to_pos(i), vial)

                        #map vial name to grid position
                        setattr(self, vial + "_pos", self.index_to_pos(i))

                    except Exception as e:
                        raise InitializationError(f"{self.name}: Error when mapping. Ensure csv is formatted correctly. {e}")

                    vials.add(vial)

                i += 1

    def index_to_pos(self, index):
        """
        Given index (0 to 47) returns grid position (A1 - H6)
        """
        if index < 0 or index > 47:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid grid index!")

        cols = ["A", "B", "C", "D", "E", "F", "G", "H"]
        return cols[index//6] + str(index % 6 + 1)
    
    def pos_to_index(self, coordinate):
        """
        Given grid position (A1 - H6) return index (0 to 47)
        """
        if coordinate[0] not in ["A", "B", "C", "D", "E", "F", "G", "H"] or coordinate[1] not in ["1", "2", "3", "4", "5", "6", "7", "8"]:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid grid position!")

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

    def to_csv(self):
        #loop through all attributes
        self.disp_rack_df.to_csv("disp_rack_updated.csv")

    def get_vial_name_by_pos(self, pos):
        if hasattr(self, pos):
            return getattr()

    def set_vial_name_by_pos(self, pos):
        pass

    def get_vial_by_name(self, name):
        pass

    def set_vial_by_name(self, name):
        pass