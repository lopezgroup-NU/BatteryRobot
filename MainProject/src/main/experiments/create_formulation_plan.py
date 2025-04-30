import csv
import pandas as pd
from utils.MathUtils import get_water_V
from config.source_rack import SourceRack
from config.disp_rack import DispRack

def create_formulation(plan_file, source_rack_file):
    """
    Currently based off of new_diverse_candidates.csv

    Takes in a file and creates a formulation plan similar to formulation.csv
    Formulation plan should always be checked before being executed

    """

    # initialize new formulation plan csv
    columns = ["Experiment","Target_vial","Sources","Volumes_mL","Solids","Weights_g","Heat","Time_h"]
    plan_df = pd.DataFrame(columns=columns)
    plan_df.set_index('Experiment', inplace=True)

    # store rows that are physically impossible to make
    cannot_rows = []
    # store dropped rows that are possible to make but could not be made
    # could be due to not amount of solution/space on deck
    dropped_formulations_columns = ["Experiment","TFSI","FSI","NO3","CLO4","SO4","AC", "H2O"]
    dropped_df = pd.DataFrame(columns=dropped_formulations_columns)
    dropped_df.set_index('Experiment', inplace=True)

    # assume sources are already on source rack and source_rack.csv configured accordingly
    source_rack = SourceRack(source_rack_file)

    # read plan and extract match column names to reagent
    in_df = pd.read_csv(plan_file)
    sources = tuple(in_df.columns)
    tfsi_name = ""
    fsi_name = ""
    no3_name = ""
    clo4_name = ""
    so4_name = ""
    ac_name = ""

    for source in sources:
        if "TFSI" in source.upper():
            tfsi_name = source
        elif "FSI" in source.upper():
            fsi_name = source
        elif "NO3" in source.upper():
            no3_name = source
        elif "CLO4" in source.upper():
            clo4_name = source
        elif "SO4" in source.upper():
            so4_name = source
        elif "AC" in source.upper():
            ac_name = source

    components = [tfsi_name, fsi_name, no3_name, clo4_name, so4_name, ac_name]
    # create our own disp_rack, initialize every cell to empty first
    disp_rack_curr = 0
    disp_rack_max = 48
    disp_rack = [["e" for _ in range(8)] for _ in range(6)]
    # loop thrrough input file
    for i, row in enumerate(in_df.itertuples(), start=1):
        print(
            [
            str(getattr(row, tfsi_name)),
            str(getattr(row, fsi_name)),
            str(getattr(row, no3_name)),
            str(getattr(row, clo4_name)),
            str(getattr(row, so4_name)),
            str(getattr(row, ac_name)),
        ]
        )
        vols = get_water_V(
            float(getattr(row, tfsi_name)),
            float(getattr(row, fsi_name)),
            float(getattr(row, no3_name)),
            float(getattr(row, clo4_name)),
            float(getattr(row, so4_name)),
            float(getattr(row, ac_name)),
        )
        vols = [round(vol, 2) for vol in vols]
        if (sum(vols[:-1]) > 5)  or any(vol < 0 for vol in vols):
            cannot_rows.append(i)
            continue

        # do the volume_concentration thing for the experiment_name
        comps = ["TFSI", "FSI", "NO3", "CLO4", "SO4", "AC"]
        concs = [
            str(getattr(row, tfsi_name)),
            str(getattr(row, fsi_name)),
            str(getattr(row, no3_name)),
            str(getattr(row, clo4_name)),
            str(getattr(row, so4_name)),
            str(getattr(row, ac_name)),
        ]

        experiment_name = ""
        for comp, conc in zip(comps, concs):  
            if float(conc) > 0:
                if experiment_name:
                    experiment_name += "_"
                
                conc_val = float(conc)
                whole_part = int(conc_val)
                decimal_part = int((conc_val - whole_part) * 100)
                formatted_conc = f"{whole_part}p{decimal_part:02d}m"

                experiment_name += f"{comp}_{formatted_conc}"

        # check space on disp_rack first 
        if disp_rack_curr == disp_rack_max:
            dropped_df.loc[experiment_name] = vols
            continue
        
        # must make sure names on source rack.csv is equal to what henry's is
        # e.g. if Henry say's "LiTFSI", we have to use "LiTFSI_x" as well where x is the 
        # id of that vial, e.g. LiTFSI_1, LiTFSI_2 etc
        # check sources 
        source_list = ""
        vol_list = ""

        drop = False
        for name, vol in zip(components + ["H2O"], vols):
            # source rack should be passed by reference
            # make changes to source rack in the rack_checker
            result = rack_checker(source_rack, name, vol)
            if len(result) == 0:
                drop = True
                break
            print(result)
            for source, vol in result:
                source_list = source_list + source
                vol_list = vol_list + vol

        if drop:
            dropped_df.loc[experiment_name] = vols
            continue 

        # add new entry to formulation df
        new_row = {
            "Target_vial": DispRack.index_to_pos(disp_rack_curr),
            "Sources": source_list.strip(),
            "Volumes_mL": vol_list.strip(),
            "Solids": "",
            "Weights_g": "",
            "Heat": True,
            "Time_h": "0.5"
        }

        plan_df.loc[experiment_name] = new_row

        # volume is 0 as hasnt been made yet. concentration is 1 as placeholder
        entry = f"{experiment_name} 0 1"
        row = disp_rack_curr % 6
        col = 7 - disp_rack_curr // 6  # Get column (0-7)
        disp_rack[row][col] = entry

        # have to skip index 6, which corresponds to B1
        disp_rack_curr = disp_rack_curr + 1 if disp_rack_curr != 5 else disp_rack_curr + 2

    if cannot_rows:
        print(f"Rows that are impossible to make (1-indexed): {str(cannot_rows)}")

    # write to gen_disp_rack.csv
    with open('config/gen_disp_rack.csv', 'w', newline='') as disp_file:
        writer = csv.writer(disp_file)
        writer.writerows(disp_rack)

    # write to gen_formulation.csv
    plan_df.to_csv("gen_formulation.csv") 
    dropped_df.to_csv("dropped_formulation_vols.csv")

    print("Generated plan. See gen_formulation.csv and gen_disp_rack.csv")

def rack_checker(rack, source_name, desired_vol):
    """
    Helper function to check source rack for source availability
    """
    num = 1
    sources = {}
    remaining_vol = desired_vol
    
    # loop through all vials with the same base name (e.g., water1, water2, etc.)
    while True:
        reagent_name = f"{source_name}_{str(num)}"
        pos = rack.get_vial_by_name(reagent_name)   
        if not pos:
            print(reagent_name)
            break
            
        _, vol, _ = rack.get_vial_by_pos(pos)
        
        if remaining_vol > 0 and vol > 0:
            use_vol = min(remaining_vol, vol)
            sources[pos] = use_vol
            
            remaining_vol -= use_vol
            new_vol = vol - use_vol
            
            rack.set_vial_by_pos(pos, new_vol)
            
        if remaining_vol <= 0:
            break
            
        num += 1
    
    if remaining_vol > 0:
        return {}
    
    formatted_result = []
    for pos, vol in sources.items():
        formatted_result.append((f"{pos} ", f"{vol} "))
    
    return formatted_result