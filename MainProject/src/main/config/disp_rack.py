import pandas as pd
from utils.ExceptionUtils import *
from pathlib import Path
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

    def __init__(self, csv_path):
        #no duplicates
        self.name = "DispRack"
        self.rack_max_index = 47
        self.purge_sources = {}
        self.solution_vols = {}

        df = pd.read_csv(csv_path, header=None)
        self.path = Path(csv_path)
        self.update_path = self.path.with_name(self.path.stem + "_updated.csv")
        self.df = df
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
                    self.purge_sources[self.index_to_pos(i)] = 8
                else: 
                    if len(el.split()) != 3:
                        print(el)
                        raise InitializationError(f"{self.name}: Each vial with contents must have 3 items: vial_name, volume, and concentration")       

                    vial, vol, conc = el.split()

                    if vial in vials:
                        raise InitializationError(f"{self.name}: No duplicate vial names!")

                    # map vial name to pos 
                    setattr(self, vial, self.index_to_pos(i))

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

    @classmethod
    def index_to_pos(cls, index):
        """
        Given index (0 to 47) returns grid position (A1 - H6)
        """
        if index < 0 or index > 47:
            raise ContinuableRuntimeError(f"{cls.__name__}: Enter valid grid index!")

        cols = ["A", "B", "C", "D", "E", "F", "G", "H"]
        return cols[index//6] + str(index % 6 + 1)
    
    @classmethod
    def pos_to_index(cls, pos):
        """
        Given grid position (A1 - H6) return index (0 to 47)
        """
        if pos[0] not in ["A", "B", "C", "D", "E", "F", "G", "H"] or pos[1] not in ["1", "2", "3", "4", "5", "6", "7", "8"]:
            raise ContinuableRuntimeError(f"{cls.__name__}: Enter valid grid position!")

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
        return mapping[pos[0]] * 6 + int(pos[1]) - 1

    def update_csv(self, pos, new_vol, new_name = None, new_conc = None):
        """
        update dataframe. update vial at position pos with new_vol. New_vol is required
        If changing entry, e.g. new solution, new_name should contain name of new solution, and new_conc
        should be it's corresponding concentration
        """

        # mapping reversed because pd dataframe is reversed
        mapping = {
            "A": 7,
            "B": 6,
            "C": 5,
            "D": 4,
            "E": 3,
            "F": 2,
            "G": 1,
            "H": 0,
        }

        col = mapping[pos[0]]
        row = int(pos[1]) - 1

        # set entry to e i.e. empty
        if new_name == "e":
            self.df.loc[row, col] = "e"
        else:
            if new_name or new_conc:
                if not new_name or not new_conc:
                    raise ContinuableRuntimeError(f"{self.name}: New concentration needed for new name!")
                self.df.loc[row, col] = f"{new_name} {new_vol} {new_conc}"
            else:
                prev = self.df.loc[row, col].split()

                # assume prior entry present
                if len(prev) == 3:
                    new = f"{prev[0]} {new_vol} {prev[2]}"
                    self.df.loc[row, col] = new

                # if reach here, error. must have new_name and new_conc
                else:
                    raise ContinuableRuntimeError(f"{self.name}: New concentration and name needed!")

        self.df.to_csv(self.update_path)

    def get_vial_by_name(self, name):
        """
        Returns vial pos if vial exists 
        """
        if not hasattr(self, name):
            return None
        
        # returns pos
        return getattr(self, name)
    
    def get_vial_by_pos(self, pos):
        """
        Given pos, return vial information (name, vol, conc)
        """
        if not hasattr(self, pos):
            raise ValueError(f"{self.name}: No vial information found at position {pos}")
        
        name = getattr(self, pos)
        vol = getattr(self, name + "_vol")
        conc = getattr(self, name + "_conc")

        return name, vol, conc


    def set_vial_by_pos(self, pos, vol, name = None, conc = None):
        """
        Given pos, update vial information (vol, conc)
        Vol should always change if name and conc are None.
        """
        # update existing entry
        if not name:
            name = getattr(self, pos)
            setattr(self, name + "_vol", vol)
            self.update_csv(pos, vol)

        # if new name, new entry
        else:
            if not conc:
                raise ValueError(f"{self.name}: Concentration information needed!")
            #delete all prior information related to current pos
            self.del_vial_by_pos(pos)
            setattr(self, name + "_vol", vol)
            setattr(self, name + "_conc", conc)
            setattr(self, name + "_pos", pos)
            setattr(self, pos, name)
            self.update_csv(pos, vol, name, conc)


    def del_vial_by_pos(self, pos):
        """
        Given pos, delete vial and all associated information (vol, conc)
        """
        if not hasattr(self, pos):
            raise ValueError(f"{self.name}: No vial to delete at position {pos}")

        name = getattr(self, pos)
        delattr(self, name + "_vol")
        delattr(self, name + "_conc")
        delattr(self, name + "_pos")
        delattr(self, pos)
        self.update_csv(pos, "e")

    def get_sol_vols(self):
        """
        Using dataframe, get volumes of solutions
        Return as dictionary of pos: volume
        Solutions defined as any non empty, non purge vial slot.
        """
        self.sol_vols = {}

        for i in range(7, -1, -1):
            for j in range(6):
                entry = self.df.loc[j,i].split()
                if len(entry) == 3:
                    vol = float(entry[1])
                    idx = (7 - i) * 6 + j
                    pos = self.index_to_pos(idx)
                    self.sol_vols[pos] = vol

        return self.sol_vols

