"""
mapping solutions to indexes of rack_asp_official 
"""

class AspRack():
    """
    Upon initialization, input mapping string to map contents to vials of asp_rack
    
    vial indexing is as follows. The entire rack is a 6x8 grid. However, some slots contain no vials,
    as the robot arm cannot reach them. Rows are labelled A-F, columns are labelled 1-8
    
    AspRack slots:               AspRack (v means vial, x means no vial):
    
    A8 A7 A6 A5 A4 A3 A2 A1      v v v v v x x x
    B8 B7 B6 B5 B4 B3 B2 B1      v v v v v x x x
    C8 C7 C6 C5 C4 C3 C2 C1  --> v v v v v x x x
    D8 D7 D6 D5 D4 D3 D2 D1      v v v v x x x x
    E8 E7 E6 E5 E4 E3 E2 E1      v v v x x x x x
    F8 F7 F6 F5 F4 F3 F2 F1      v v x x x x x x    
    
    The diagram on the right indicates that the right two most columns(A1 - F2) have no vials in them.
    Other slots that have no vial are C3, D3, E3, F3, D4, E4, F4, E5, F5, F6.
    
    On the robot deck, there will be two uncapped vials at positions A3 and B3. These are not meant to contain
    any liquids as they act as cap holders.
    
    Numerical mapping of AspRack:
    
    24 18 12 6 0 x x x
    25 19 13 7 1 x x x
    26 20 14 8 2 x x x
    27 21 15 9 x x x x
    28 22 16 x x x x x
    29 23 x  x x x x x
    
    Enter an input string mapping the contents of each vial. If multiple vials contain the same liquid,
    number them. E.g. water1 water2 etc.
    
    In total there are 24 vials. As such, the input string should contain 24 names, one for each of the liquids
    stored in the vials.
    
    E.g. 1) "water1 water2 NaCl1 NaCl2 ..." will map the vial at index 0, 1, 2, 6 to water1, water2, NaCl1, and NaCl2
    respectively, and so on.
    
    E.g. 2) If you want water to occupy the first row of vials, the input string would be:
    "water1 a b water2 c d e water3 f g h i water4 j k l m n water5 o p q r s"
    
    (random letters are other liquids)
    
    Once mapped, these can be used to position the robot arm according to the rack_asp_official locator.
    For example if you have an object of AspRack called rack, and you want to move the arm to the location of water1:
    simply: rob.goto_safe(rack_asp_official[rack.water1])
    """
    def __init__(self, mapping):
        map_list = mapping.split()
        
        #list of vials, according to diagram above
        index_list = [0, 1, 2, 6, 7, 8, 9, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
        
        #no duplicates and must be 24 
        if len(map_list) != 24:
            raise Exception(f"Input mapping string must have 24 elements! Your's has: {len(map_list)}")
        
        if len(map_list) != len(set(map_list)):
            raise Exception("No duplicates!")
        
        for i in range(len(index_list)):
            setattr(self, map_list[i], index_list[i])
            
#demo        
if __name__ == "__main__":
    rack = AspRack("water1 water2 d e f g h i j k water3 l m n o p q r s t u v w x")
    
    #
    assert rack.water1 == 0
    assert rack.water2 == 1
    assert rack.water3 == 15
    
    