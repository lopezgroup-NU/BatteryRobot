from Locator import *
# plate_locations.py -- plate rig (triplet): where the arm goes for Mux Cycle fills.
# Data only. After editing, restart the Thonny backend (a live session keeps the
# old values).
# None = none.
# needs is filled in (a "none" run never reads this file).

# ---- source vial (uncapped) ----
# SOURCE_VIAL_APPROACH = [1021, 35980, 39915, 15937]   # above the vial; simulate pulls its 1 mL of air here
SOURCE_VIAL = [1021, 35980, 39915, 21512] 
SOURCE_VIAL_APPROACH = [1021, 35980, 39919, 21512]            # tip in the liquid; draw aspirates here

# ---- where the tip dispenses into each cell ----
UNIFORM_Z = 20179
CELL_LOCATIONS = [[80, 11990, 30490, 20180], [80, 9930, 28793, 20390], [80, 8200, 27650, 20419], [80, 6712, 26800, 20238], [77, 12924, 32732, 20368], [78, 10894, 31231, 20586], [74, 9136, 30126, 20348], [76, 7688, 29445, 20621], [143, 14370, 35489, 20349], [146, 12028, 33688, 20617], [164, 10216, 32602, 20480], [164, 8852, 32081, 20650], [252, 16198, 38589, 20491], [252, 13593, 36557, 20738], [266, 11628, 35322, 20409], [267, 10121, 34701, 21068], [310, 20400, 44187, 20505], [340, 15617, 39720, 21132], [342, 13354, 38268, 21125], [353, 11665, 37438, 20768], [559, 20616, 45358, 12592], [640, 19016, 44405, 20413], [635, 15412, 41419, 20931], [650, 13516, 40415, 21015]]
# CELL_LOCATIONS = [
#     [-18, 11937, 30355, UNIFORM_Z],  # 1A  0
#     [-14, 9853, 28686, UNIFORM_Z],  # 1B  1
#     None,  # 1C  2
#     None,  # 1D  3
#     [-14, 12875, 32687, UNIFORM_Z],  # 2A  4
#     None,  # 2B  5
#     None,  # 2C  6
#     None,  # 2D  7
#     None,  # 3A  8
#     None,  # 3B  9
#     None,  # 3C  10
#     None,  # 3D  11
#     None,  # 4A  12
#     None,  # 4B  13
#     None,  # 4C  14
#     None,  # 4D  15
#     None,  # 5A  16
#     None,  # 5B  17
#     None,  # 5C  18
#     None,  # 5D  19
#     None,  # 6A  20
#     None,  # 6B  21
#     None,  # 6C  22
#     None,  # 6D  23
# ]
# CELL_LOCATIONS = [[-948, 30231, 35926, 2800], [-1042, 32191, 37454, 2800], [-1128, 33846, 38541, 2800], [-1213, 35291, 39260, 2800],
#                   [-937, 30863, 37454, 2800], [-1026, 32777, 38998, 2800], [-1110, 34421, 40149, 2800], [-1192, 35877, 40959, 2800],
#                   [-922, 31399, 38916, 2800], [-1007, 33283, 40505, 2800], [-1086, 34926, 41742, 2800], [-1165, 36398, 42671, 2800],
#                   [-901, 31849, 40318, 2800], [-982, 33715, 41974, 2800], [-1058, 35361, 43319, 2800], [-1132, 36852, 44392, 2800],
#                   [-877, 32218, 41661, 2800], [-954, 34073, 43404, 2800], [-1025, 35726, 44873, 2800], [-1095, 37237, 46114, 2800],
#                   [-849, 32510, 42946, 2800], [-921, 34359, 44788, 2800], [-988, 36020, 46397, 2800], [-1051, 37551, 47823, 2800]]

# ---- above each cell: draw passes through it, simulate stops here ----
# None -> each CELL_LOCATIONS point with z raised by APPROACH_LIFT counts.
# Or a 24-row 2D list like CELL_LOCATIONS if you teach them yourself.
CELL_APPROACHES = None
APPROACH_LIFT = 2500

# ---- where the arm waits after a simulate run ----
# (a draw run already ends at safe_zone when it drops the tip)
# None -> Locator.safe_zone
PARK_LOCATION = None