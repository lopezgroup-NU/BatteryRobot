import os
import json
import numpy as np
import pandas as pd 
from pymongo import MongoClient
from pathlib import Path

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

        # more than one salt
        if len(stem_split) != 3:
            continue

        salt, conc, test_type = stem_split

        # first part should be salt name
        salts.add(salt)

        # get conc
        conc = conc[:-1]
        dec_conc = float(conc.replace("p", "."))

        # keep track
        if salt in salts_to_conc_list:
            salts_to_conc_list[salt].append(dec_conc)
        else:
            salts_to_conc_list[salt] = [dec_conc]

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

        salt_and_conc.add((salt, conc, test_num))

    return salts, salt_and_conc, salts_to_conc_list

class MongoConn:
    """
    A class to manage a MongoDB connection using PyMongo.
    """

    def __init__(self, uri="mongodb://localhost:27017/", db_name="atomdb"):
        """
        Initialize the MongoDBConnection with a MongoDB URI and a default database name.

        :param uri: MongoDB connection URI (default: "mongodb://localhost:27017/")
        :param db_name: Database name to use (default: "atomdb")
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

    Current collections - cv_data and geis_data
    """

    def __init__(self, uri="mongodb://localhost:27017/", db_name="atomdb"):
        self.conn = MongoConn(uri=uri, db_name=db_name)

    def add_cv_data(self, folder, ignore_first=True):
        """
        Set ignore_first to True if you want to ignore the first of the three values
        when calculating average 
        """
        csv_files = [f for f in os.listdir(folder) if f.endswith(".csv")]
        salts, salt_and_conc, salt_to_conc_list = parse_files(csv_files, type="cv")
        collection = self.conn.get_collection("cv_data")

        for tup in salt_and_conc:
            salt, conc, test_num = tup
            
            # rebuild file name
            if test_num == 1:
                prefix  = ""
            else:
                prefix = str(test_num)
            
            name = f"{str(salt)}_{str(conc)}m_{str(test_num)}"

            cv_diff = []
            for i in range(3):
                file_name = f"{salt}_{conc}m_{prefix}cv{str(i)}.csv"
                path = folder / Path(file_name)
                
                try:
                    df = pd.read_csv(path, index_col='# Point')
                except:
                    continue

                positive_peak_index, zero_cross_index, negative_peak_index = find_peaks_and_zero_crossings(df)
                x = df["Vf"]
                y = df['Im']

                cv_diff.append(abs(x[positive_peak_index] - x[negative_peak_index]))

            if len(cv_diff) == 1:
                avg_cv_diff = cv_diff[0]
            elif ignore_first:
                # ignore first value
                avg_cv_diff = sum(cv_diff[1:]) / (len(cv_diff) - 1) 
            else:
                avg_cv_diff = sum(cv_diff) / (len(cv_diff))

            collection.update_one(
                {"name": name},
                {"$set": {"avg_cv_diff": avg_cv_diff,
                          "cv_diff": cv_diff,
                          "ignore_first": ignore_first}}, 
                upsert=True
            )

    def add_geis_data(self, folder, ignore_first=True):
        """
        Set ignore_first to True if you want to ignore the first of the three values
        when calculating average 
        """
        csv_files = [f for f in os.listdir(folder) if f.endswith(".csv")]
        salts, salt_and_conc, salt_to_conc_list = parse_files(csv_files, type="geis")
        collection = self.conn.get_collection("geis_data")

        for tup in salt_and_conc:
            salt, conc, test_num = tup

            # rebuild file name
            if test_num == 1:
                prefix  = ""
            else:
                prefix = str(test_num)

            name = f"{str(salt)}_{str(conc)}m_{str(test_num)}"

            all_conductivity = []
            for i in range(3):
                file_name = f"{salt}_{conc}m_{prefix}geis{str(i)}.csv"
                path = folder / Path(file_name)

                try:
                    df = pd.read_csv(path, index_col='# point')
                except:
                    continue

                # extract zreal, compute conductivity
                df_no_negatives = df[df.reflected_zimag >=0]
                min_index = df_no_negatives['reflected_zimag'].idxmin()  # Get the index of the minimum value
                zreal = df_no_negatives['zreal'].loc[min_index]  # Use .loc to get the value at that index
                conductivity =  6.06007673/zreal  
                all_conductivity.append(conductivity)
                
            if len(all_conductivity) == 1:
                avg_conductivity = all_conductivity[0]
            elif ignore_first:
                # ignore first value
                avg_conductivity = sum(all_conductivity[1:]) / (len(all_conductivity) - 1) 
            else:
                avg_conductivity = sum(all_conductivity) / len(all_conductivity)

            collection.update_one(
                {"name": name},
                {"$set": {"avg_conductivity": avg_conductivity,
                          "conductivity": all_conductivity,
                          "ignore_first": ignore_first}}, 
                upsert=True
            )

    def update_ignore(self, collection_name, ignore_first:bool):
        """
        Update ignore_first (in the collection) with the given ignore_first for all data in 
        the given collection. 
        Also changes the average value if ignore_first is different than before.
        """
        collection = self.conn.get_collection(collection_name)
        if collection_name == "cv_data":
            data_field, avg_field = "cv_diff", "avg_cv_diff"
            
        else: # collection_name == "geis_data"
            data_field, avg_field = "conductivity", "avg_conductivity"

        for doc in collection.find():
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
            with open(f"{collection_name}.json", "w", encoding="utf-8") as file:
                file.write(json_output)
        return json_output
    
    def drop_data(self, collection_name):
        """
        Drop all data from a certain collection (i.e. table)

        Current collections - cv_data and geis_data
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

    def plot_cv(self):
        pass

    def plot_eis(self):
        pass