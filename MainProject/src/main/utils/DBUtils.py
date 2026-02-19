import os
import json
import time
import numpy as np
import pandas as pd 
from pymongo import MongoClient
from pathlib import Path
from .MathUtils import get_water_weight_from_components
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

F = 96485  # C/mol
R = 8.314  # J/mol·K

def butler_volmer(eta, j0, alphaC, n=2, T=298.15):
    #alpha A
    return j0 *  - np.exp(-(alphaC) * n * F * eta / (R * T))

def fit_butler_volmer(eta_data, current_data, T=298.15, n = 1, plot=False): #change name to tafel_fit
    """Fits the Butler-Volmer equation to experimental data."""
    def bv_fit_func(eta, i0, alphaC):
        return butler_volmer(eta, i0, alphaC, n=n, T=T)
    initial_guess = [1, 0.5]
    bounds = ([.00001, 0.0], [200, 1])
    popt, pcov = curve_fit(bv_fit_func, eta_data, current_data, p0=initial_guess, bounds=bounds,maxfev=500000)

    return popt, pcov
    
def find_zero_crossings_from_lists(x_list, y_list):
    """
    Finds zero crossings in two parallel lists: x-values and y-values.
    Parameters:
        x_list (list of float): X-axis values (e.g., voltage).
        y_list (list of float): Y-axis values (e.g., current).
    Returns:
        List of (x, 0.0) points where the curve crosses the x-axis.
    """
    zero_crossings = []
    for i in range(len(y_list) - 1):
        x1, y1 = x_list[i], y_list[i]
        x2, y2 = x_list[i + 1], y_list[i + 1]
        # Check for sign change
        if y1 * y2 < 0:
            x_zero = x1 - y1 * (x2 - x1) / (y2 - y1)
            zero_crossings.append((x_zero, 0.0))
        elif y1 == 0:
            zero_crossings.append((x1, 0.0))
    return zero_crossings

def find_peaks_and_zero_crossings(data):
    # Find the index of the first occurrence of zero in 'Vf'
    zero_index = np.argmax(data['Vf'] >= 0)
    # Find the positive peak (maximum after the first zero crossing)
    positive_peak_index = np.argmax(data['Im'][zero_index:]) + zero_index
    # Find where the voltage crosses 0 after the positive peak
    # We are looking for the first zero-crossing point after the positive peak
    zero_cross_index = np.argmax(np.diff(np.sign(data['Vf'][positive_peak_index:])) != 0) + positive_peak_index
    # Find the negative peak (minimum after the 0V crossing)
    negative_peak_index = np.argmin(data['Im'][zero_cross_index:]) + zero_cross_index
    return positive_peak_index, zero_cross_index, negative_peak_index

def kinetic_fit(cv_file):
    data_first = pd.read_csv(cv_file)
    positive_peak_index, zero_cross_index, negative_peak_index = find_peaks_and_zero_crossings(data_first)
    E = data_first['Vf']
    I = data_first['Im']*1000/0.020
    E = E[negative_peak_index:]
    I = I[negative_peak_index:]
    switch_x = find_zero_crossings_from_lists(E.to_numpy(), I.to_numpy())
    E = E  - switch_x[0][0]
    mask =  (E <= -.06)
    if len(E[mask])>2: 
        E = E[mask]
        I = I[mask]
        params, covariance = fit_butler_volmer(E, I, T=298.15, plot=True)
        return (switch_x[0][0], f"{params[0]:.3e}", f"{params[1]:.5f}")
    else: return(switch_x[0][0], np.nan, np.nan)

def cv_interpret(filename, reverse_peak = False):
    df_file = filename
    df = pd.read_csv(df_file, index_col='# Point')

    positive,zero,negative = find_peaks_and_zero_crossings(df)

    targ_max = 0.000024
    targ_min = -0.000024
    im_col = df["Im"]
    vf_col = df["Vf"]

    if reverse_peak:
        im_colPositive = im_col[positive:zero]
        im_colNegative = im_col[negative:]

        vf_colPositive = vf_col[positive:zero]
        vf_colNegative = vf_col[negative:]
    else:
        im_colPositive = im_col[:positive]
        im_colNegative = im_col[zero:negative]

        vf_colPositive = vf_col[:positive]
        vf_colNegative = vf_col[zero:negative]

    #get xmax
    #translate column by target and get absolute values. find index of minimum (closest to 0)
    im_col_translated_pos = (im_colPositive - targ_max).abs()
    min_idx_pos = im_col_translated_pos.idxmin()
    vf_max = vf_colPositive.loc[min_idx_pos]  # Use .loc to get the value at that index

    #get xmin
    im_col_translated_neg = (im_colNegative + targ_max).abs()
    min_idx_neg = im_col_translated_neg.idxmin()
    vf_min = vf_colNegative.loc[min_idx_neg]  # Use .loc to get the value at that index

    vf_diff = vf_max-vf_min

    return(vf_diff,vf_max,vf_min )

def parse_files(file_list, type="cv"):
    """
    Currently only works for single salts! Assume three tests per salt.

    type is either cv or geis
    """
    salts_to_conc_list = {}
    salts = set()

    # tuple of salts and concentrations
    salt_and_conc = set()

    for file in file_list:
        stem = Path(file).stem
        stem_split = stem.split("_")

        salt = []
        conc = []
        test_type = []
        # more than one salt
        if len(stem_split) != 3:
            for index, value in enumerate(stem_split[:-1]):
                if index % 2 == 0:  # 0-based index for 1st, 3rd, 5th, 7th...
                    salt.append(value)
                elif index % 2 == 1:  # 0-based index for 2nd, 4th, 6th, 8th...
                    conc.append(value)
            test_type = stem_split[-1]     
        else:
            salt, conc, test_type = stem_split
            salt = [salt]
            conc = [conc]
            test_type = test_type

        # first part should be salt name
        salts.add(tuple(salt))

        # get conc
        dec_conc = [(s.replace("p", ".")) for s in conc]
        dec_conc = [(s.replace("m", "")) for s in dec_conc]

        # keep track
        if tuple(salt) in salts_to_conc_list:
            salts_to_conc_list[tuple(salt)].append(tuple(dec_conc))
        else:
            salts_to_conc_list[tuple(salt)] = [tuple(dec_conc)]

        # from test_type, determine the test number for this test
        if type == "cv":
            suffix_length = 3
        else:
            suffix_length = 5

        test_num = test_type[:-suffix_length]

        if test_num == "":
            test_num = 1
        else:
            test_num = int(test_num)
        salt_and_conc.add((tuple(salt), tuple(dec_conc), test_num))

    return salts, salt_and_conc, salts_to_conc_list

class MongoConn:
    """
    A class to manage a MongoDB connection using PyMongo.
    """

    def __init__(self, uri="mongodb://localhost:27018/", db_name="test_db"):
        """
        Initialize the MongoDBConnection with a MongoDB URI and a default database name.

        :param uri: MongoDB connection URI (default: "mongodb://localhost:27018/")
        :param db_name: Database name to use (default: "test_db")
        """
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        """
        Create a MongoClient instance and select the specified database.
        """
        self.client = MongoClient(self.uri)
        self.db = self.client[self.db_name]

    def get_collection(self, collection_name, db_name=None):
        """
        Return a collection object from either the default database or a specified one.

        :param collection_name: The name of the collection to retrieve.
        :param db_name: (Optional) name of a database if different from the default.
        :return: A MongoDB collection object.
        """
        if db_name:
            return self.client[db_name][collection_name]
        return self.db[collection_name]
    
class MongoQuery:
    """
    Queries to operate on CV and EIS data.

    collections ~= tables for a sql db
    document ~= row/tuple/record of information for a sql db 

    Current collections - data (contains both eis and cv data)
    """

    def __init__(self, uri="mongodb://localhost:27017/", db_name="test_db"):
        self.conn = MongoConn(uri=uri, db_name=db_name)

    def listify(self, a, order = 1):
        """
        listify will convert a to a list of the order specified by "order", and leave it alone otherwise. listify assumes that the list has even nesting; i.e, that every element of "a" contains the same number of lists
        
        :param self: Description
        :param a: variable to be turned into a list
        :param order: level of nesting; 1 = normal list, 2 = list of lists, etc. listify will convert
        """
        currentListOrder = 0
        sublist = a
        while(isinstance(sublist, list)):
            sublist = a[0]
            currentListOrder += 1

        if order > currentListOrder:
            return [a]
        else:
            return a

    def add_same_cv_data_once(self, cv_file_list, ignore_first=True, components = {"AC":0, "FSI": 0, "ClO4": 0, "SO4": 0, "NO3": 0, "TFSI": 0}):
        
        """
        Add cv data to the database, but instead of adding/overwriting previous tests with the same formulation, this simply adds to a list of existing data

        Current collections - cv_data and geis_data

        Set dump_to_file = True if you want to dump the json output into a file
        """
        collection = self.conn.get_collection("data")
        docs = list(collection.find({}))
        #print(docs[0])

        #FIRST: we do all the same stuff as the regular add_cv_data_once function does

        all_cv_diff = []
        low_end_cv = []
        high_end_cv = []

        all_cv_diff_rev = []
        low_end_cv_rev = []
        high_end_cv_rev = []
        collection = self.conn.get_collection("data")

        file_names = [path.name for path in cv_file_list]
        file_named = file_names[0][:-4]
        salts, salt_and_conc, salt_to_conc_list = parse_files(file_names, type="cv")
        salt, conc, test_num = salt_and_conc[0]
        
        for i, path in enumerate(cv_file_list):
            vf_diff,vf_max,vf_min = cv_interpret(path, reverse_peak=False)
            all_cv_diff.append(vf_diff)
            low_end_cv.append(vf_min)
            high_end_cv.append(vf_max)

            vf_diff_rev,vf_max_rev,vf_min_rev = cv_interpret(path, reverse_peak=True)
            all_cv_diff_rev.append(vf_diff_rev)
            low_end_cv_rev.append(vf_min_rev)
            high_end_cv_rev.append(vf_max_rev)
            
            # overP, i0, alpha_c = kinetic_fit(path)
            # all_overP.append(overP)
            # all_i0.append(i0)
            # all_alpha_c.append(alpha_c)

            # get timestamp of latest file for specific run
            # i.e. if two files, get timestamp of second
            time_stamp = os.path.getctime(path)
            time_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_stamp))

            #do the same, for temp
            df = pd.read_csv(path)
            if 'temp(C)' in df.columns:
                temp = df['temp(C)'].iloc[0]
            else:
                temp = 20

        if len(all_cv_diff) == 1:
                avg_cv_diff = all_cv_diff[0]
                avg_cv_low = low_end_cv[0]
                avg_cv_high = high_end_cv[0]

                avg_cv_diff_rev = all_cv_diff_rev[0]
                avg_cv_low_rev= low_end_cv_rev[0]
                avg_cv_high_rev = high_end_cv_rev[0]

                # avg_overP = all_overP[0]
                # avg_i0 = all_i0[0]
                # avg_alpha_c = all_alpha_c[0]

        elif ignore_first:
            # ignore first value
            def compute_avg_ignore(lst):
                # Auto-cast all elements to float if possible
                try:
                    lst = [float(x) for x in lst]
                except (ValueError, TypeError):
                    raise ValueError("List contains non-numeric values that can't be converted.")
                return sum(lst[1:]) / (len(lst) - 1)
            avg_cv_diff = compute_avg_ignore(all_cv_diff)
            avg_cv_low =  compute_avg_ignore(low_end_cv)
            avg_cv_high =  compute_avg_ignore(high_end_cv)
            
            avg_cv_diff_rev = compute_avg_ignore(all_cv_diff_rev)
            avg_cv_low_rev=  compute_avg_ignore(low_end_cv_rev)
            avg_cv_high_rev =  compute_avg_ignore(high_end_cv_rev)
            
            # avg_overP =  compute_avg_ignore(all_overP)
            # avg_i0 =  compute_avg_ignore(all_i0)
            # avg_alpha_c =  compute_avg_ignore(all_alpha_c)

        else:
            def compute_avg(lst):
                try:
                    lst = [float(x) for x in lst]
                except (ValueError, TypeError):
                    raise ValueError("List contains non-numeric values that can't be converted.")
                return sum(lst) / (len(lst))
            avg_cv_diff = compute_avg(all_cv_diff)
            avg_cv_low =  compute_avg(low_end_cv)
            avg_cv_high =  compute_avg(high_end_cv)

            avg_cv_diff_rev = compute_avg(all_cv_diff_rev)
            avg_cv_low_rev=  compute_avg(low_end_cv_rev)
            avg_cv_high_rev =  compute_avg(high_end_cv_rev)

            # avg_overP =  compute_avg(all_overP)
            # avg_i0 =  compute_avg(all_i0)
            # avg_alpha_c =  compute_avg(all_alpha_c)

        components_dict = {}
        for i in range(len(salt)):
            components_dict[salt[i]] = float(conc[i])
        
        water_weight = get_water_weight_from_components(components_dict)
        valid_flag = True
        if len(all_cv_diff) != 0:
            update_vals = [
                        avg_cv_diff, #avg_cv_diff 0
                        all_cv_diff, #cv_diff 1
                        avg_cv_high, #avg_highV 2
                        high_end_cv, #highV 3
                        avg_cv_low, #avg_lowV 4
                        low_end_cv, #lowV 5

                        avg_cv_diff_rev, #avg_cv_diff_rev 6
                        all_cv_diff_rev, #cv_diff_rev 7
                        avg_cv_high_rev, #avg_highV_rev 8
                        high_end_cv_rev, #highV_rev 9
                        avg_cv_low_rev, #avg_lowV_rev 10
                        low_end_cv_rev, #lowV_rev 11

                        ignore_first, #ignore_first 12
                        time_stamp, #cv_date_uploaded 13
                        components_dict, #components 14
                        water_weight, #water_weight 15 
                        False, #precipitated_out 16
                        temp, #temp(C) 17
                        "Pt", #electrode_used 18
                        [str(path) for path in cv_file_list], #paths 19
                        valid_flag, #valid_flag 20
                        None #cv_error 21
                        ]
                        
            """
            avg_cv_diff
            cv_diff
            avg_highV
            highV
            avg_lowV
            lowV

            avg_cv_diff_rev
            cv_diff_rev
            avg_highV_rev
            highV_rev
            avg_lowV_rev
            lowV_rev

            ignore_first
            cv_date_uploaded
            components
            water_weight
            precipitated_out
            temp(C)
            electrode_used
            paths
            valid_flag
            """
            if len(all_cv_diff) == 3:
                update_vals[21] = all_cv_diff[2] - all_cv_diff[1] #cv_error
                

                collection.update_one(
                {"name": file_named},
                {"$set": {"cv_error": all_cv_diff[2] - all_cv_diff[1],
                            "components": components_dict}}, 
                upsert=True
            )

        #SECOND: we go through all of the entries, check to find an exact match of components, then convert each element of the data to a list. 

        for entry in docs:
            if entry["components"] == components:
                collection.update_one(

                    {"name": entry["name"]},
                
                {"$set": {"avg_cv_diff": [*self.listify(entry["avg_cv_diff"]), update_vals[0]], #we need to unpack the list using *var so that we don't get nesting
                        "cv_diff": [*self.listify(entry["cv_diff"]), update_vals[1]], # some values are initially 
                        "avg_highV": [*self.listify(entry["avg_highV"]), update_vals[2]],
                        "highV": [*self.listify(entry["highV"]), update_vals[3]],
                        "avg_lowV": [*self.listify(entry["avg_lowV"]), update_vals[4]],
                        "lowV": [*self.listify(entry["lowV"]), update_vals[5]],

                        "avg_cv_diff_rev": [*self.listify(entry["avg_cv_diff_rev"], 2), update_vals[6]],
                        "cv_diff_rev": [*self.listify(entry["cv_diff_rev"], 2), update_vals[7]],
                        "avg_highV_rev": [*self.listify(entry["avg_highV_rev"], 2), update_vals[8]],
                        "highV_rev": [*self.listify(entry["highV_rev"], 2), update_vals[9]],
                        "avg_lowV_rev": [*self.listify(entry["avg_lowV_rev"], 2), update_vals[10]],
                        "lowV_rev": [*self.listify(entry["lowV_rev"], 2), update_vals[11]],

                        


                        # "avg_overP": avg_overP,
                        # "overP": all_overP,
                        # "avg_i0": avg_i0,
                        # "i0": all_i0,
                        # "avg_alpha_c": avg_alpha_c,
                        # "alpha_c": all_alpha_c,
                        "ignore_first": [*self.listify(entry["ignore_first"]), update_vals[12]],
                        "cv_date_uploaded": [*self.listify(entry["cv_date_uploaded"]), update_vals[13]],
                        #"components": [*self.listify(entry["components"], 2), update_vals[14]],         # components should be identical; if not, uncomment this
                        "water_weight": [*self.listify(entry["water_weight"]), update_vals[15]],
                        "precipitated_out": [*self.listify(entry["precipitated_out"]), update_vals[16]],
                        "temp(C)": [*self.listify(entry["temp(C)"]), update_vals[17]],
                        "electrode_used": [*self.listify(entry["electrode_used"]), update_vals[18]],
                        "paths": [*self.listify(entry["paths"]), update_vals[19]],
                        "valid_flag": [*self.listify(entry["valid_flag"]), update_vals[20]],
                        "cv_error": [*self.listify(entry["cv_error"]), update_vals[20]]
                        }}, 
                upsert=True

                )

    
    def add_formulation(self, components = {"AC":0, "FSI": 0, "ClO4": 0, "SO4": 0, "NO3": 0, "TFSI": 0}):
        
        """
        Get all data from a certain collection (i.e. table)

        Current collections - cv_data and geis_data

        Set dump_to_file = True if you want to dump the json output into a file
        """
        collection = self.conn.get_collection("data")
        docs = list(collection.find({}))
        #print(docs[0])


        all_cv_diff = []
        low_end_cv = []
        high_end_cv = []

        all_cv_diff_rev = []
        low_end_cv_rev = []
        high_end_cv_rev = []
        collection = self.conn.get_collection("data")

        file_names = [path.name for path in cv_file_list]
        file_named = file_names[0][:-4]
        salts, salt_and_conc, salt_to_conc_list = parse_files(file_names, type="cv")
        salt, conc, test_num = salt_and_conc[0]
        
        for i, path in enumerate(cv_file_list):
            vf_diff,vf_max,vf_min = cv_interpret(path, reverse_peak=False)
            all_cv_diff.append(vf_diff)
            low_end_cv.append(vf_min)
            high_end_cv.append(vf_max)

            vf_diff_rev,vf_max_rev,vf_min_rev = cv_interpret(path, reverse_peak=True)
            all_cv_diff_rev.append(vf_diff_rev)
            low_end_cv_rev.append(vf_min_rev)
            high_end_cv_rev.append(vf_max_rev)
            
            # overP, i0, alpha_c = kinetic_fit(path)
            # all_overP.append(overP)
            # all_i0.append(i0)
            # all_alpha_c.append(alpha_c)

            # get timestamp of latest file for specific run
            # i.e. if two files, get timestamp of second
            time_stamp = os.path.getctime(path)
            time_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_stamp))

            #do the same, for temp
            df = pd.read_csv(path)
            if 'temp(C)' in df.columns:
                temp = df['temp(C)'].iloc[0]
            else:
                temp = 20

        if len(all_cv_diff) == 1:
                avg_cv_diff = all_cv_diff[0]
                avg_cv_low = low_end_cv[0]
                avg_cv_high = high_end_cv[0]

                avg_cv_diff_rev = all_cv_diff_rev[0]
                avg_cv_low_rev= low_end_cv_rev[0]
                avg_cv_high_rev = high_end_cv_rev[0]

                # avg_overP = all_overP[0]
                # avg_i0 = all_i0[0]
                # avg_alpha_c = all_alpha_c[0]

        elif ignore_first:
            # ignore first value
            def compute_avg_ignore(lst):
                # Auto-cast all elements to float if possible
                try:
                    lst = [float(x) for x in lst]
                except (ValueError, TypeError):
                    raise ValueError("List contains non-numeric values that can't be converted.")
                return sum(lst[1:]) / (len(lst) - 1)
            avg_cv_diff = compute_avg_ignore(all_cv_diff)
            avg_cv_low =  compute_avg_ignore(low_end_cv)
            avg_cv_high =  compute_avg_ignore(high_end_cv)
            
            avg_cv_diff_rev = compute_avg_ignore(all_cv_diff_rev)
            avg_cv_low_rev=  compute_avg_ignore(low_end_cv_rev)
            avg_cv_high_rev =  compute_avg_ignore(high_end_cv_rev)
            
            # avg_overP =  compute_avg_ignore(all_overP)
            # avg_i0 =  compute_avg_ignore(all_i0)
            # avg_alpha_c =  compute_avg_ignore(all_alpha_c)

        else:
            def compute_avg(lst):
                try:
                    lst = [float(x) for x in lst]
                except (ValueError, TypeError):
                    raise ValueError("List contains non-numeric values that can't be converted.")
                return sum(lst) / (len(lst))
            avg_cv_diff = compute_avg(all_cv_diff)
            avg_cv_low =  compute_avg(low_end_cv)
            avg_cv_high =  compute_avg(high_end_cv)

            avg_cv_diff_rev = compute_avg(all_cv_diff_rev)
            avg_cv_low_rev=  compute_avg(low_end_cv_rev)
            avg_cv_high_rev =  compute_avg(high_end_cv_rev)

            # avg_overP =  compute_avg(all_overP)
            # avg_i0 =  compute_avg(all_i0)
            # avg_alpha_c =  compute_avg(all_alpha_c)

        components_dict = {}
        for i in range(len(salt)):
            components_dict[salt[i]] = float(conc[i])
        
        water_weight = get_water_weight_from_components(components_dict)
        valid_flag = True
        if len(all_cv_diff) != 0:
            update_vals = [
                        avg_cv_diff, #avg_cv_diff 0
                        all_cv_diff, #cv_diff 1
                        avg_cv_high, #avg_highV 2
                        high_end_cv, #highV 3
                        avg_cv_low, #avg_lowV 4
                        low_end_cv, #lowV 5

                        avg_cv_diff_rev, #avg_cv_diff_rev 6
                        all_cv_diff_rev, #cv_diff_rev 7
                        avg_cv_high_rev, #avg_highV_rev 8
                        high_end_cv_rev, #highV_rev 9
                        avg_cv_low_rev, #avg_lowV_rev 10
                        low_end_cv_rev, #lowV_rev 11

                        ignore_first, #ignore_first 12
                        time_stamp, #cv_date_uploaded 13
                        components_dict, #components 14
                        water_weight, #water_weight 15 
                        False, #precipitated_out 16
                        temp, #temp(C) 17
                        "Pt", #electrode_used 18
                        [str(path) for path in cv_file_list], #paths 19
                        valid_flag, #valid_flag 20
                        None #cv_error 21
                        ]
                        
            """
            avg_cv_diff
            cv_diff
            avg_highV
            highV
            avg_lowV
            lowV

            avg_cv_diff_rev
            cv_diff_rev
            avg_highV_rev
            highV_rev
            avg_lowV_rev
            lowV_rev

            ignore_first
            cv_date_uploaded
            components
            water_weight
            precipitated_out
            temp(C)
            electrode_used
            paths
            valid_flag
            """
            if len(all_cv_diff) == 3:
                update_vals[21] = all_cv_diff[2] - all_cv_diff[1] #cv_error
                

                collection.update_one(
                {"name": file_named},
                {"$set": {"cv_error": all_cv_diff[2] - all_cv_diff[1],
                            "components": components_dict}}, 
                upsert=True
            )


        for entry in docs:
            if entry["components"] == components:
                collection.update_one(

                    {"name": entry["name"]},
                
                {"$set": {"avg_cv_diff": [entry["avg_cv_diff"], update_vals[0]],
                        "cv_diff": [entry["cv_diff"], update_vals[1]],
                        "avg_highV": [entry["avg_highV"], update_vals[2]],
                        "highV": [entry["highV"], update_vals[3]],
                        "avg_lowV": [entry["avg_lowV"], update_vals[4]],
                        "lowV": [entry["lowV"], update_vals[5]],

                        "avg_cv_diff_rev": [entry["avg_cv_diff_rev"], update_vals[6]],
                        "cv_diff_rev": [entry["cv_diff_rev"], update_vals[7]],
                        "avg_highV_rev": [entry["avg_highV_rev"], update_vals[8]],
                        "highV_rev": [entry["highV_rev"], update_vals[9]],
                        "avg_lowV_rev": [entry["avg_lowV_rev"], update_vals[10]],
                        "lowV_rev": [entry["lowV_rev"], update_vals[11]],

                        


                        # "avg_overP": avg_overP,
                        # "overP": all_overP,
                        # "avg_i0": avg_i0,
                        # "i0": all_i0,
                        # "avg_alpha_c": avg_alpha_c,
                        # "alpha_c": all_alpha_c,
                        "ignore_first": [entry["ignore_first"], update_vals[12]],
                        "cv_date_uploaded": [entry["cv_date_uploaded"], update_vals[13]],
                        "components": [entry["components"], update_vals[14]],
                        "water_weight": [entry["water_weight"], update_vals[15]],
                        "precipitated_out": [entry["precipitated_out"], update_vals[16]],
                        "temp(C)": [entry["temp(C)"], update_vals[17]],
                        "electrode_used": [entry["electrode_used"], update_vals[18]],
                        "paths": [entry["paths"], update_vals[19]],
                        "valid_flag": [entry["valid_flag"], update_vals[20]],
                        "cv_error": [entry["cv_error"], update_vals[20]]
                        }}, 
                upsert=True

                )



    def add_cv_data_one(self, cv_file_list, ignore_first=True):
        all_cv_diff = []
        low_end_cv = []
        high_end_cv = []

        all_cv_diff_rev = []
        low_end_cv_rev = []
        high_end_cv_rev = []
        collection = self.conn.get_collection("data")

        file_names = [path.name for path in cv_file_list]
        file_named = file_names[0][:-4]
        salts, salt_and_conc, salt_to_conc_list = parse_files(file_names, type="cv")
        salt, conc, test_num = salt_and_conc[0]
        
        for i, path in enumerate(cv_file_list):
            vf_diff,vf_max,vf_min = cv_interpret(path, reverse_peak=False)
            all_cv_diff.append(vf_diff)
            low_end_cv.append(vf_min)
            high_end_cv.append(vf_max)

            vf_diff_rev,vf_max_rev,vf_min_rev = cv_interpret(path, reverse_peak=True)
            all_cv_diff_rev.append(vf_diff_rev)
            low_end_cv_rev.append(vf_min_rev)
            high_end_cv_rev.append(vf_max_rev)
            
            # overP, i0, alpha_c = kinetic_fit(path)
            # all_overP.append(overP)
            # all_i0.append(i0)
            # all_alpha_c.append(alpha_c)

            # get timestamp of latest file for specific run
            # i.e. if two files, get timestamp of second
            time_stamp = os.path.getctime(path)
            time_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_stamp))

            #do the same, for temp
            df = pd.read_csv(path)
            if 'temp(C)' in df.columns:
                temp = df['temp(C)'].iloc[0]
            else:
                temp = 20

        if len(all_cv_diff) == 1:
                avg_cv_diff = all_cv_diff[0]
                avg_cv_low = low_end_cv[0]
                avg_cv_high = high_end_cv[0]

                avg_cv_diff_rev = all_cv_diff_rev[0]
                avg_cv_low_rev= low_end_cv_rev[0]
                avg_cv_high_rev = high_end_cv_rev[0]

                # avg_overP = all_overP[0]
                # avg_i0 = all_i0[0]
                # avg_alpha_c = all_alpha_c[0]

        elif ignore_first:
            # ignore first value
            def compute_avg_ignore(lst):
                # Auto-cast all elements to float if possible
                try:
                    lst = [float(x) for x in lst]
                except (ValueError, TypeError):
                    raise ValueError("List contains non-numeric values that can't be converted.")
                return sum(lst[1:]) / (len(lst) - 1)
            avg_cv_diff = compute_avg_ignore(all_cv_diff)
            avg_cv_low =  compute_avg_ignore(low_end_cv)
            avg_cv_high =  compute_avg_ignore(high_end_cv)
            
            avg_cv_diff_rev = compute_avg_ignore(all_cv_diff_rev)
            avg_cv_low_rev=  compute_avg_ignore(low_end_cv_rev)
            avg_cv_high_rev =  compute_avg_ignore(high_end_cv_rev)
            
            # avg_overP =  compute_avg_ignore(all_overP)
            # avg_i0 =  compute_avg_ignore(all_i0)
            # avg_alpha_c =  compute_avg_ignore(all_alpha_c)

        else:
            def compute_avg(lst):
                try:
                    lst = [float(x) for x in lst]
                except (ValueError, TypeError):
                    raise ValueError("List contains non-numeric values that can't be converted.")
                return sum(lst) / (len(lst))
            avg_cv_diff = compute_avg(all_cv_diff)
            avg_cv_low =  compute_avg(low_end_cv)
            avg_cv_high =  compute_avg(high_end_cv)

            avg_cv_diff_rev = compute_avg(all_cv_diff_rev)
            avg_cv_low_rev=  compute_avg(low_end_cv_rev)
            avg_cv_high_rev =  compute_avg(high_end_cv_rev)

            # avg_overP =  compute_avg(all_overP)
            # avg_i0 =  compute_avg(all_i0)
            # avg_alpha_c =  compute_avg(all_alpha_c)

        components_dict = {}
        for i in range(len(salt)):
            components_dict[salt[i]] = float(conc[i])
        
        water_weight = get_water_weight_from_components(components_dict)
        valid_flag = True
        if len(all_cv_diff) != 0:
            collection.update_one(
                {"name": file_named},
                
                {"$set": {"avg_cv_diff": avg_cv_diff,
                        "cv_diff": all_cv_diff,
                        "avg_highV": avg_cv_high,
                        "highV": high_end_cv,
                        "avg_lowV": avg_cv_low,
                        "lowV": low_end_cv,

                        "avg_cv_diff_rev": avg_cv_diff_rev,
                        "cv_diff_rev": all_cv_diff_rev,
                        "avg_highV_rev": avg_cv_high_rev,
                        "highV_rev": high_end_cv_rev,
                        "avg_lowV_rev": avg_cv_low_rev,
                        "lowV_rev": low_end_cv_rev,

                        # "avg_overP": avg_overP,
                        # "overP": all_overP,
                        # "avg_i0": avg_i0,
                        # "i0": all_i0,
                        # "avg_alpha_c": avg_alpha_c,
                        # "alpha_c": all_alpha_c,
                        "ignore_first": ignore_first,
                        "cv_date_uploaded": time_stamp,
                        "components": components_dict,
                        "water_weight": water_weight,
                        "precipitated_out": False,
                        "temp(C)": temp,
                        "electrode_used"
                        "paths": [str(path) for path in cv_file_list],
                        "valid_flag": valid_flag
                        }}, 
                upsert=True
            )

            if len(all_cv_diff) == 3:
                collection.update_one(
                {"name": file_named},
                {"$set": {"cv_error": all_cv_diff[2] - all_cv_diff[1],
                            "components": components_dict}}, 
                upsert=True
            )

    def add_cv_data(self, folder, ignore_first=True):
        """
        Set ignore_first to True if you want to ignore the first of the three values
        when calculating average 
        """
        csv_files = [f for f in os.listdir(folder) if f.endswith(".csv")]
        salts, salt_and_conc, salt_to_conc_list = parse_files(csv_files, type="cv")
        collection = self.conn.get_collection("data")

        for tup in salt_and_conc:
            salt, conc, test_num = tup
            
            # rebuild file name
            if test_num == 1:
                prefix  = ""
            else:
                prefix = str(test_num)
            
            name = []
            for i in range(len(salt)):
                name.append(f"{str(salt[i])}_{str(conc[i])}m")
            # Add the test number at the end
            name = ("_".join(name) + f"_{prefix}") if prefix != "" else "_".join(name)
            file_named = name.replace(".", "p")
            all_cv_diff = []
            low_end_cv = []
            high_end_cv = []

            all_cv_diff_rev = []
            low_end_cv_rev = []
            high_end_cv_rev = []

            all_overP = []
            all_i0 = []
            all_alpha_c = []
            paths = []
            for i in range(3):
                file_name = f"{file_named}_cv{str(i)}.csv"
                path = folder / Path(file_name)
                if os.path.exists(path):
                    paths.append(str(path))
                    vf_diff,vf_max,vf_min = cv_interpret(path, reverse_peak=False)
                    all_cv_diff.append(vf_diff)
                    low_end_cv.append(vf_min)
                    high_end_cv.append(vf_max)

                    vf_diff_rev,vf_max_rev,vf_min_rev = cv_interpret(path, reverse_peak=True)
                    all_cv_diff_rev.append(vf_diff_rev)
                    low_end_cv_rev.append(vf_min_rev)
                    high_end_cv_rev.append(vf_max_rev)
                    
                    # overP, i0, alpha_c = kinetic_fit(path)
                    # all_overP.append(overP)
                    # all_i0.append(i0)
                    # all_alpha_c.append(alpha_c)

                    # get timestamp of latest file for specific run
                    # i.e. if two files, get timestamp of second
                    time_stamp = os.path.getctime(path)
                    time_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_stamp))

                    #do the same, for temp
                    df = pd.read_csv(path)
                    if 'temp(C)' in df.columns:
                        temp = df['temp(C)'].iloc[0]
                    else:
                        temp = 20

            if len(all_cv_diff) == 1:
                avg_cv_diff = all_cv_diff[0]
                avg_cv_low = low_end_cv[0]
                avg_cv_high = high_end_cv[0]

                avg_cv_diff_rev = all_cv_diff_rev[0]
                avg_cv_low_rev= low_end_cv_rev[0]
                avg_cv_high_rev = high_end_cv_rev[0]

                # avg_overP = all_overP[0]
                # avg_i0 = all_i0[0]
                # avg_alpha_c = all_alpha_c[0]

            elif ignore_first:
                # ignore first value
                def compute_avg_ignore(lst):
                    # Auto-cast all elements to float if possible
                    try:
                        lst = [float(x) for x in lst]
                    except (ValueError, TypeError):
                        raise ValueError("List contains non-numeric values that can't be converted.")
                    return sum(lst[1:]) / (len(lst) - 1)
                avg_cv_diff = compute_avg_ignore(all_cv_diff)
                avg_cv_low =  compute_avg_ignore(low_end_cv)
                avg_cv_high =  compute_avg_ignore(high_end_cv)
                
                avg_cv_diff_rev = compute_avg_ignore(all_cv_diff_rev)
                avg_cv_low_rev=  compute_avg_ignore(low_end_cv_rev)
                avg_cv_high_rev =  compute_avg_ignore(high_end_cv_rev)
                
                # avg_overP =  compute_avg_ignore(all_overP)
                # avg_i0 =  compute_avg_ignore(all_i0)
                # avg_alpha_c =  compute_avg_ignore(all_alpha_c)

            else:
                def compute_avg(lst):
                    try:
                        lst = [float(x) for x in lst]
                    except (ValueError, TypeError):
                        raise ValueError("List contains non-numeric values that can't be converted.")
                    return sum(lst) / (len(lst))
                avg_cv_diff = compute_avg(all_cv_diff)
                avg_cv_low =  compute_avg(low_end_cv)
                avg_cv_high =  compute_avg(high_end_cv)

                avg_cv_diff_rev = compute_avg(all_cv_diff_rev)
                avg_cv_low_rev=  compute_avg(low_end_cv_rev)
                avg_cv_high_rev =  compute_avg(high_end_cv_rev)

                # avg_overP =  compute_avg(all_overP)
                # avg_i0 =  compute_avg(all_i0)
                # avg_alpha_c =  compute_avg(all_alpha_c)

            components_dict = {}
            for i in range(len(salt)):
                components_dict[salt[i]] = float(conc[i])
           
            water_weight = get_water_weight_from_components(components_dict)
            valid_flag = True
            if len(all_cv_diff) != 0:
                collection.update_one(
                    {"name": file_named},
                    {"$set": {"avg_cv_diff": avg_cv_diff,
                            "cv_diff": all_cv_diff,
                            "avg_highV": avg_cv_high,
                            "highV": high_end_cv,
                            "avg_lowV": avg_cv_low,
                            "lowV": low_end_cv,

                            "avg_cv_diff_rev": avg_cv_diff_rev,
                            "cv_diff_rev": all_cv_diff_rev,
                            "avg_highV_rev": avg_cv_high_rev,
                            "highV_rev": high_end_cv_rev,
                            "avg_lowV_rev": avg_cv_low_rev,
                            "lowV_rev": low_end_cv_rev,

                            # "avg_overP": avg_overP,
                            # "overP": all_overP,
                            # "avg_i0": avg_i0,
                            # "i0": all_i0,
                            # "avg_alpha_c": avg_alpha_c,
                            # "alpha_c": all_alpha_c,
                            "ignore_first": ignore_first,
                            "cv_date_uploaded": time_stamp,
                            "components": components_dict,
                            "water_weight": water_weight,
                            "precipitated_out": False,
                            "temp(C)": temp,
                            "paths": paths,
                            "valid_flag": valid_flag
                            }}, 
                    upsert=True
                )

                if len(all_cv_diff) == 3:
                    collection.update_one(
                    {"name": file_named},
                    {"$set": {"cv_error": all_cv_diff[2] - all_cv_diff[1],
                              "components": components_dict}}, 
                    upsert=True
                )

    def add_geis_data_one(self, geis_file_list, ignore_first=True):
        all_conductivity = []
        collection = self.conn.get_collection("data")

        file_names = [path.name for path in geis_file_list]
        file_named = file_names[0][:-6]
        salts, salt_and_conc, salt_to_conc_list = parse_files(file_names, type="cv")
        salt, conc, test_num = salt_and_conc[0]
        for i, path in enumerate(geis_file_list):
            df = pd.read_csv(path, index_col='# point')
            # extract zreal, compute conductivity
            df_no_negatives = df[df.reflected_zimag >=0]
            min_index = df_no_negatives['reflected_zimag'].idxmin()  # Get the index of the minimum value
            zreal = df_no_negatives['zreal'].loc[min_index]  # Use .loc to get the value at that index
            conductivity =  6.06007673/zreal  
            all_conductivity.append(conductivity)

            # get timestamp of latest file for specific run
            time_stamp = os.path.getmtime(path)
            time_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_stamp))
            #do the same, for temp
            df = pd.read_csv(path)
            if 'temp(C)' in df.columns:
                temp = df['temp(C)'].iloc[0]
            else:
                temp = 20
    
        if len(all_conductivity) == 1:
                avg_conductivity = all_conductivity[0]
        elif ignore_first:
            # ignore first value
            avg_conductivity = sum(all_conductivity[1:]) / (len(all_conductivity) - 1) 
        else:
            avg_conductivity = sum(all_conductivity) / len(all_conductivity)

        components_dict = {}
        for i in range(len(salt)):
            components_dict[salt[i]] = float(conc[i])

        water_weight = get_water_weight_from_components(components_dict)
        valid_flag = True
        if len(all_conductivity) != 0:
            collection.update_one(
                {"name": file_named},
                {"$set": {"avg_conductivity": avg_conductivity,
                        "conductivity": all_conductivity,
                        "ignore_first": ignore_first,
                        "geis_date_uploaded": time_stamp,
                        "components": components_dict,
                        "water_weight": water_weight,
                        "precipitated_out": False,
                        "temp(C)": temp,
                        "paths": [str(path) for path in geis_file_list],
                        "valid_flag": valid_flag
                        }}, 
                upsert=True
            )

            if len(all_conductivity) == 3:
                collection.update_one(
                {"name": file_named},
                {"$set": {"geis_error": all_conductivity[2] - all_conductivity[1],
                        "components": components_dict}}, 
                upsert=True
            )

    def add_geis_data(self, folder, ignore_first=True):
        """
        Set ignore_first to True if you want to ignore the first of the three values
        when calculating average 
        """
        csv_files = [f for f in os.listdir(folder) if f.endswith(".csv")]
        salts, salt_and_conc, salt_to_conc_list = parse_files(csv_files, type="geis")
        collection = self.conn.get_collection("data")

        for tup in salt_and_conc:
            salt, conc, test_num = tup
            # rebuild file name
            if test_num == 1:
                prefix  = ""
            else:
                prefix = str(test_num)

            name = []
            for i in range(len(salt)):
                name.append(f"{str(salt[i])}_{str(conc[i])}m")
            # Add the test number at the end
            name = ("_".join(name) + f"_{prefix}") if prefix != "" else "_".join(name)
            file_named = name.replace(".", "p")

            all_conductivity = []
            paths = []
            for i in range(3):
                file_name = f"{file_named}_geis{str(i)}.csv"
                path = folder / Path(file_name)

                if os.path.exists(path):
                    paths.append(str(path))
                    df = pd.read_csv(path, index_col='# point')
                    # extract zreal, compute conductivity
                    df_no_negatives = df[df.reflected_zimag >=0]
                    min_index = df_no_negatives['reflected_zimag'].idxmin()  # Get the index of the minimum value
                    zreal = df_no_negatives['zreal'].loc[min_index]  # Use .loc to get the value at that index
                    conductivity =  6.06007673/zreal  
                    all_conductivity.append(conductivity)

                    # get timestamp of latest file for specific run
                    time_stamp = os.path.getmtime(path)
                    time_stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time_stamp))
                    #do the same, for temp
                    df = pd.read_csv(path)
                    if 'temp(C)' in df.columns:
                        temp = df['temp(C)'].iloc[0]
                    else:
                        temp = 20
                
            if len(all_conductivity) == 1:
                avg_conductivity = all_conductivity[0]
            elif ignore_first:
                # ignore first value
                avg_conductivity = sum(all_conductivity[1:]) / (len(all_conductivity) - 1) 
            else:
                avg_conductivity = sum(all_conductivity) / len(all_conductivity)

            components_dict = {}
            for i in range(len(salt)):
                components_dict[salt[i]] = float(conc[i])

            water_weight = get_water_weight_from_components(components_dict)
            valid_flag = True
            if len(all_conductivity) != 0:
                collection.update_one(
                    {"name": file_named},
                    {"$set": {"avg_conductivity": avg_conductivity,
                            "conductivity": all_conductivity,
                            "ignore_first": ignore_first,
                            "geis_date_uploaded": time_stamp,
                            "components": components_dict,
                            "water_weight": water_weight,
                            "precipitated_out": False,
                            "temp(C)": temp,
                            "paths": paths,
                            "valid_flag" : valid_flag
                            }}, 
                    upsert=True
                )

                if len(all_conductivity) == 3:
                    collection.update_one(
                    {"name": file_named},
                    {"$set": {"geis_error": all_conductivity[2] - all_conductivity[1],
                              "components": components_dict}}, 
                    upsert=True
                )

    def update_ignore(self, collection_name, ignore_first:bool):
        """
        Update ignore_first (in the collection) with the given ignore_first for all data in 
        the given collection. 
        Also changes the average value if ignore_first is different than before.
        """
        collection = self.conn.get_collection(collection_name)
        if collection_name == "data":
            data_field, avg_field = "cv_diff", "avg_cv_diff"
            
        else: # collection_name == "geis_data"
            data_field, avg_field = "conductivity", "avg_conductivity"

        for doc in collection.find():
            # in case doc doesnt have ignore_first, skip to avoid crash
            try:
                # if already same as specified, just skip
                if doc["ignore_first"] == ignore_first:
                    continue

                data = doc[data_field]
                if len(data) == 1:
                    new_value = data[0]
                elif ignore_first:
                    # ignore first value
                    new_value = sum(data[1:]) / (len(data) - 1) 
                else:
                    new_value = sum(data) / len(data)

                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {avg_field: new_value,
                            "ignore_first": ignore_first}}, 
                )

            except:
                continue

    
    def set_saturated_out(self, file):
        """
        Takes in file of salts where saturated out = true
        Adds them to db
        Add breakdown of components as well

        Example: file.txt

        TFSI_5m
        TFSI_3m
        """
        
        collection = self.conn.get_collection("data")

        with open(file, 'r') as file:
            for line in file:
                line = line.strip()
                if line:
                    s = line.split("_")
                    components_dict = {}
                    
                    for i in range(0, len(s), 2):
                        salt = s[i]
                        conc_str = s[i+1]
                        # remove the trailing m
                        conc_str = conc_str[:-1]
                        conc_str = conc_str.replace('p', '.')
                        conc = float(conc_str)
                        components_dict[salt] = conc

                    water_weight = get_water_weight_from_components(components_dict)

                    collection.update_one(
                        {"name": line},
                        {"$set": {"precipitated_out": True,
                                  "components": components_dict,
                                  "water_weight": water_weight}}, 
                        upsert=True
                    )

    def get_data(self, collection_name, dump_to_file = False):
        """
        Get all data from a certain collection (i.e. table)

        Current collections - cv_data and geis_data

        Set dump_to_file = True if you want to dump the json output into a file
        """
        collection = self.conn.get_collection(collection_name)
        docs = list(collection.find({}))

        # Convert to JSON. default=str will convert ObjectIds and datetimes to strings.
        json_output = json.dumps(docs, default=str, indent=4)

        if dump_to_file:
            with open(f"{collection_name}_zeeIsTestingThis.json", "w", encoding="utf-8") as file:
                json.dump(docs, file, default=str, indent=4)

        
    
    def drop_data(self, collection_name):
        """
        Drop all data from a certain collection (i.e. table)

        Current collections - data
        """
        collection = self.conn.get_collection(collection_name)
        collection.drop()

    def drop_one(self, collection_name, name):
        """
        Given name, drop the row from given collection
        """
        collection = self.conn.get_collection(collection_name)
        result = collection.delete_one({"name": name})

        if result.deleted_count > 0:
            print(f"Deleted {name}")
        else:
            print("No deletion occurred")

    def update_temps(self, file_path):
        """
        Give summary file, update temps based on that
        """
        df = pd.read_csv(file_path)
        temp_dict = dict(zip(df['test name'], df['temp']))
        collection = self.conn.get_collection("data")
        for document in collection.find():
            # names in the summary are appended with _cv0, _cv1 or _cv2
            # our db doesnt have that as it aggregates all 3
            # additionally, it is possible that the machine stopped early,
            # this code accounts for that by updating with the latest one 
            for i in range(3):
                name = document.get('name') + f"_cv{str(i)}"
                if name in temp_dict:
                    collection.update_one(
                        {'_id': document['_id']},
                        {'$set': {'temp(C)': temp_dict[name]}}
                    )
