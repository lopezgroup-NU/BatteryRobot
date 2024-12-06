import pandas as pd
from utils.ExceptionUtils import *

class SourceRack():
    """
    mapping solutions to indexes of rack_source_official 

    Input mapping strings to map contents to vials of asp_rack
    
    vial indexing is as follows. The entire rack is a 6x5 pos. However, some slots contain no vials,
    as the robot arm cannot reach them. Rows are labelled 1-6, Columns are labelled A-E (right to left)
    
    SourceRack slots:               SourceRack (v means vial, x means no vial):
    
    E1 D1 C1 B1 A1       v v v v v 
    E2 D2 C2 B2 A2       v v v v v 
    E3 D3 C3 B3 A3   --> v v v v v
    E4 D4 C4 B4 A4       v v v v x
    E5 D5 C5 B5 A5       v v v x x
    E6 D6 C6 B6 A6       v x x x x     
    
    Per the diagram on the right, the slots that have no vial are D6, C6, B6, A6, A4, A5, B5.
    
    Numerical mapping of SourceRack:
    
    23 18 12 6 0 
    24 19 13 7 1 
    25 20 14 8 2 
    26 21 15 9 x 
    27 22 16 x x 
    28 x  x  x x 
    
    Enter an input string mapping the contents of each vial. If multiple vials contain the same liquid,
    number them. E.g. water1 water2 etc.
    
    In total there are 23 vials. As such, the input string should contain 23 names, one for each of the liquids
    stored in the vials.
    
    E.g. 1) "water1 water2 NaCl1 NaCl2 ..." will map the vial at index 0, 1, 2, 6 to water1, water2, NaCl1, and NaCl2
    respectively, and so on.
    
    E.g. 2) If you want water to occupy the first row of vials, the input string would be:
    "water1 a b water2 c d e water3 f g h i water4 j k l m n water5 o p q r"
    
    (random letters are other liquids or e if empty)
    
    Once mapped, these can be used to position the robot arm according to the rack_asp_official locator.
    For example if you have an object of SourceRack called rack, and you want to move the arm to the location of water1:
    simply: rob.goto_safe(rack_asp_official[rack.water1])
    
    Input a second string, vols, containing the corresponding volume of content in each vial
    Input a third string, concs, containing the corresponding concentration of content in each vial
    
    vials = "KCl1 KCl2"
    vols = "10 5"
    concs = "0.5 0.1" 
    
    means 10ml of fluids in the vial named KCl1 at 0.5M, and 5ml of fluids in the vial named KCl2 at 0.1M. 
    """
    
    rack_max_index = 29
    name = "SourceRack"
    
    def __init__(self, csv_path):
        #no duplicates
        df = pd.read_csv(csv_path, header=None)
        self.source_rack_df = df
        self.csv_path_updated = csv_path + "_updated" #when rack state is updated, store df here

        self.invalid_index = set()
        vials = set()

        i = 0 #track index
        df = df.iloc[:, ::-1]
        for col in df:
            for el in df[col]:
                if i > self.rack_max_index:
                    raise InitializationError(f"{self.name}: Too many indexes, fix rack csv file.")

                if el == 'x': # x to signify robot cannot reach position. n means no vial at given index. 
                    self.invalid_index.add(i)
                elif el == 'e':
                    pass
                else: 
                    if len(el.split()) != 3:
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
                        #map pos to vial name. convert index to pos, then match to vial name 
                        setattr(self, self.index_to_pos(i), vial)

                        #map vial name to pos position
                        setattr(self, vial + "_pos", self.index_to_pos(i))

                    except Exception as e:
                        raise InitializationError(f"{self.name}: Error when mapping. Ensure csv is formatted correctly. {e}")

                    vials.add(vial)

                i += 1
    
    def index_to_pos(self, index):
        """
        Given index (0 to 29) returns position (A1 - E6)
        """
        if index < 0 or index > 29 or index in self.invalid_index:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid grid index!")
        
        cols = ["A", "B", "C", "D", "E"]
        return cols[index//6] + str(index % 6 + 1)
    
    def pos_to_index(self, coordinate):
        """
        Given position (A1 - E6) return index (0 to 29)
        """
        if coordinate[0] not in ["A", "B", "C", "D", "E"] or coordinate[1] not in ["1", "2", "3", "4", "5", "6"]:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid position!")

        mapping = {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
            "E": 4
        }

        index = mapping[coordinate[0]] * 6 + int(coordinate[1]) - 1

        if index in self.invalid_index:
            raise ContinuableRuntimeError(f"{self.name}: Enter valid position!")
        else:
            return index 
#demo        
if __name__ == "__main__":
    pass
    