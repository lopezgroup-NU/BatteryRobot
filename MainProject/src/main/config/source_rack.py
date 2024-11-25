class SourceRack():
    """
    mapping solutions to indexes of rack_source_official 

    Input mapping strings to map contents to vials of asp_rack
    
    vial indexing is as follows. The entire rack is a 6x5 grid. However, some slots contain no vials,
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
    
    def __init__(self, vials, vols, concs, csv_path):        
        #no duplicates 
        if len(vials) != len(set(vials)):
            raise Exception("No duplicate names!")
        
        for i in range(len(vials)):
            #map vial name to index
            if vials[i] != "e" or vials[i] != "x":
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
        Given index (0 to 29) returns grid position (A1 - E6)
        """
        if index < 0 or index > 29:
            raise Exception("SourceRack: Enter valid grid index!")
        
        cols = ["A", "B", "C", "D", "E"]
        return cols[index//6] + str(index % 6 + 1)
    
    def grid_to_index(self, coordinate):
        """
        Given grid position (A1 - E6) return index (0 to 29)
        """
        if coordinate[0] not in ["A", "B", "C", "D", "E"] or coordinate[1] not in ["1", "2", "3", "4", "5", "6"]:
            print("Enter valid coordinates!")
            return -1 

        mapping = {
            "A": 0,
            "B": 1,
            "C": 2,
            "D": 3,
            "E": 4
        }
        return mapping[coordinate[0]] * 6 + int(coordinate[1])
        
#demo        
if __name__ == "__main__":
    pass
    