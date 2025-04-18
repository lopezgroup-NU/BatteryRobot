import csv
import pandas as pd
from MainProject.src.main.utils.MathUtils import get_weights
from config.source_rack import SourceRack
def create_formulation(plan_file, source_rack_file):
    """
    Currently based off of Henry's OLHS Triangle design csv

    Takes in a file and creates a formulation plan similar to formulation.csv
    Formulation plan should always be checked before being executed
    """

    # initialize new formulation plan
    columns = ["Experiment","Target_vial","Sources","Volumes_mL","Solids","Weights_g","Heat","Time_h"]
    plan_df = pd.DataFrame(columns=columns)
    plan_df.set_index('Experiment', inplace=True)

    disp_vials = {}
    source_vials = {}

    # store dropped rows that are possible to make but could not be made
    # could be due to not amount of solution/space on deck
    cannot_rows = []
    dropped_rows = []

    # assume sources are already on rack and source_rack.csv configured accordingly
    source_rack = SourceRack(source_rack_file)

    # create our own disp_rack, initialize every cell to empty first
    disp_rack_curr = 0
    disp_rack_max = 48
    disp_rack = [["e" for _ in range(8)] for _ in range(6)]

    #for naming e.g. N01 
    # we just assume it's N followed by two digits 01-99
    id = 1

    in_df = pd.read_csv(plan_file)
    sources = tuple(in_df.columns)
    source_names={}
    tfsi_name = ""
    fsi_name = ""
    no3_name = ""
    clo4_name = ""
    so4_name = ""
    ac_name = ""
    for source in sources:
        if "TFSI" in source.upper():
            tfsi_name = source
        if "FSI" in source.upper():
            fsi_name = source
        elif "NO3" in source.upper():
            no3_name = source
        elif "CLO4" in source.upper():
            clo4_name = source
        elif "SO4" in source.upper():
            so4_name = source
        elif "AC" in source.upper():
            ac_name = source

    for i, row in enumerate(in_df.itertuples(), start=1):
        # check returned sum not > 5
        vols = get_weights(
            getattr(row, tfsi_name),
            getattr(row, fsi_name),
            getattr(row, no3_name),
            getattr(row, clo4_name),
            getattr(row, so4_name),
            getattr(row, ac_name),
        )

        if(sum(vols) > 5):
            cannot_rows.append(i)
            continue

        # check space on disp_rack first 
        if disp_rack_curr == disp_rack_max:
            dropped_rows.append(i)
        
        components = [tfsi_name, fsi_name, no3_name, clo4_name, so4_name, ac_name, "H2O"]
        h2o_vol = 5 - sum(vols)
        vols.append(h2o_vol)

        # check sources 
        drop = False
        for name, vol in zip(components, vols):
            result = rack_checker(source_rack, name, vol)
            if result is None:
                drop = True
                break
            source_rack = result

        if drop:
            dropped_rows.append(i)
            continue 

        # now we add new entry to disp_rack 
        # TODO
        name = f"N"
        if id < 10:
            name = name + "0" + str(id)
        else:
            name = name + str(id)
        entry = f"{name} 5 1"
        id = id+1

    if cannot_rows:
        print(f"Rows with vol > 5 (1-indexed): {str(cannot_rows)}")
    if dropped_rows:
        print(f"Dropped rows (1-indexed): {str(dropped_rows)}")

    # write to disp_rack.csv
    with open('../config/gen_disp_rack.csv', 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(disp_rack)

    print("Generated plan. See gen_formulation.csv and gen_disp_rack.csv")

def rack_checker(rack, source_name, desired_vol):
    """
    Helper function to check source rack for source availability
    """
    num = 1

    while True:
        # TODO
        # loop through all with name and determine if enough
        name = f"{source_name}_{str(num)}"
        num = num + 1

    
