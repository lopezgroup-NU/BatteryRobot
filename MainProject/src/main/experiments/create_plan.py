import csv
import pandas as pd
from utils.MathUtils import get_weights
from config.source_rack import SourceRack
from config.disp_rack import DispRack
from config.heat_rack import HeatRack

def create_plan(plan_file, source_rack_file):
    """
    Currently based off of new_diverse_candidates.csv

    Takes in a file and creates a formulation plan similar to formulation.csv
    Formulation plan should always be checked before being executed

    """

    # initialize new formulation plan csv
    formulation_columns = ["Experiment","Target_vial","Sources","Volumes_mL","Solids","Weights_g","Heat","Time_h"]
    formulation_df = pd.DataFrame(columns=formulation_columns)
    formulation_df.set_index('Experiment', inplace=True)

    # initialize new experiments csv
    exp_columns = ["Experiment","Target_vial","GEIS","GEIS_Conditions","CV","CV_Conditions","CE"]
    exp_df = pd.DataFrame(columns=exp_columns)
    exp_df.set_index('Experiment', inplace=True)

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
    disp_rack[0][6] = "x"
    # loop thrrough input file

    heat_idx = 0
    max_heat_slots = 24
    for i, row in enumerate(in_df.itertuples(), start=1):
        vols = get_weights(
            float(getattr(row, tfsi_name)),
            float(getattr(row, fsi_name)),
            float(getattr(row, no3_name)),
            float(getattr(row, clo4_name)),
            float(getattr(row, so4_name)),
            float(getattr(row, ac_name)),
        )
        vols = [round(vol, 2) for vol in vols]
        if (sum(vols) > 5)  or any(vol < 0 for vol in vols):
            cannot_rows.append(i)
            continue

        water_vol = round(5 - sum(vols), 2)
        vols.append(water_vol)
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
        if disp_rack_curr == disp_rack_max or heat_idx == max_heat_slots:
            dropped_df.loc[experiment_name] = [round(v, 2) for v in vols]
            continue

        # must make sure names on source rack.csv is equal to what henry's is
        # e.g. if Henry say's "LiTFSI", we have to use "LiTFSI_x" as well where x is the
        # id of that vial, e.g. LiTFSI_1, LiTFSI_2 etc
        # check sources
        source_list = ""
        vol_list = ""

        drop = False
        temp_source_vols = {} # Store used volumes temporarily
        for name, desired_v in zip(components + ["H2O"], vols):
            if desired_v > 0.0:
                result = rack_checker(source_rack, name, desired_v)
                if not result:
                    drop = True
                    break
                for source, vol in result.items():
                    source_list += f"{source} "
                    vol_list += f"{round(vol, 2)} "
                    if source not in temp_source_vols:
                        temp_source_vols[source] = 0
                    temp_source_vols[source] += vol

        if drop:
            dropped_df.loc[experiment_name] = [round(v, 2) for v in vols]
            # Revert changes to source rack if formulation was dropped
            for source, vol in temp_source_vols.items():
                current_vol = source_rack.get_vial_by_pos(source)[1]
                source_rack.set_vial_by_pos(source, round(current_vol + vol, 2))
            continue

        # add new entry to formulation df
        new_row = {
            "Target_vial": DispRack.index_to_pos(disp_rack_curr),
            "Sources": source_list.strip(),
            "Volumes_mL": vol_list.strip(),
            "Solids": "",
            "Weights_g": "",
            "Heat": HeatRack.index_to_pos(heat_idx),
            "Time_h": "0.5"
        }

        formulation_df.loc[experiment_name] = new_row
        
        # add new entry to expriments df
        new_exp_row = {
            "Target_vial": DispRack.index_to_pos(disp_rack_curr),
            "GEIS": True,
            "GEIS_Conditions": "250000 1 0.00001",
            "CV": True,
            "CV_Conditions": "2 -2 0.020",
            "CE": False 
        }

        exp_df.loc[experiment_name] = new_exp_row        
        # volume is 0 as hasnt been made yet. concentration is 1 as placeholder
        entry = f"{experiment_name} 0 1"
        row = disp_rack_curr % 6
        col = 7 - disp_rack_curr // 6  # Get column (0-7)
        disp_rack[row][col] = entry

        # have to skip index 6, which corresponds to B1
        disp_rack_curr = disp_rack_curr + 1 if disp_rack_curr != 5 else disp_rack_curr + 2
        heat_idx += 1


    if cannot_rows:
        print(f"Rows that are impossible to make (1-indexed): {str(cannot_rows)}")

    # write to disp_rack.csv
    with open('config/disp_rack.csv', 'w', newline='') as disp_file:
        writer = csv.writer(disp_file)
        writer.writerows(disp_rack)

    # write to gen_formulation.csv
    generated_formulation_file = "formulation.csv"
    dropped_formulations_file = "dropped_formulation_vols.csv"
    generated_exp_file = "experiments.csv"

    formulation_df.to_csv(f"experiments/{generated_formulation_file}")
    exp_df.to_csv(f"experiments/{generated_exp_file}")
    dropped_df.to_csv(f"experiments/{dropped_formulations_file}")

    print(f"Generated plan. See {generated_formulation_file}, {generated_exp_file}, and disp_rack.csv")
    print(f"Dropped formulations are available in experiments/{dropped_formulations_file}. \n \
          These were dropped because of resource constraints on the source rack/heat rack, but are possible to make. \n \
          You can copy these back into the plan file and run it again")

def rack_checker(rack, source_name, desired_vol):
    """
    Helper function to check source rack for source availability
    """
    num = 1
    sources_used = {}
    remaining_vol = round(desired_vol, 2)

    # loop through all vials with the same base name (e.g., water1, water2, etc.)
    while remaining_vol > 0:
        reagent_name = f"{source_name}_{str(num)}"
        pos = rack.get_vial_by_name(reagent_name)
        if not pos:
            break

        _, vol, _ = rack.get_vial_by_pos(pos)
        vol = round(vol, 2)

        # Available volume is whatever is above 2 mL
        available_vol = max(0, vol - 2) 
        if available_vol > 0:
            use_vol = min(remaining_vol, available_vol)
            use_vol = round(use_vol, 2)
            sources_used[pos] = use_vol

            remaining_vol -= use_vol
            remaining_vol = round(remaining_vol, 2)
            new_vol = round(vol - use_vol, 2)

            rack.set_vial_by_pos(pos, new_vol)

        num += 1

    if remaining_vol > 0:
        # Revert any changes made to the rack since we couldn't fulfill the volume
        for pos, used_vol in sources_used.items():
            current_vol = rack.get_vial_by_pos(pos)[1]
            rack.set_vial_by_pos(pos, round(current_vol + used_vol, 2))
        return {}

    return sources_used

if __name__ == "__main__":
    create_plan("top_constrained_15_ori.csv", "../config/source_rack.csv")