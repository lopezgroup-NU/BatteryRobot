from north import NorthC9

class Carousel(NorthC9):
    res1 = (91,85) # reservoir 1
    res2 = (137,85) # reservoir 2
    cart1 = (68, 85) # cartridge position 1
    cart2 = (113, 85) # cartridge position 2
    cart3 = (158, 85) # cartridge position 3
    cart4 = (203,85) # cartridge position 4
    cart5 = (248,85) # cartridge position 5
    cart6 = (293,85) # cartridge position 6

    # starting volume assuming full reservoir (accounts for volume that needle cannot reach)
    res1_vol = 67.2 
    res2_vol = 67.2
    vol_purge = 19 
    #

    def __init__(self):
        pass

    def purge(self):
        if self.res1_vol >= self.vol_purge or self.res2_vol >= self.vol_purge:
            pos = self.res1 if self.res1_vol >= self.vol_purge else self.res2

            # pos now is tuple of desired reservoir
            self.move_carousel(pos[0], pos[1])

            # draw three vials worth
            # 19ml total 
            
        else:
            self.move_carousel(91, 77)