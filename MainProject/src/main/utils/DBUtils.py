import psycopg2

class DB():
    """
    Connects to existing PostgreSQL database. Default values for host and port are localhost and 5432 respectively
    Currently, theres only one user, also the superuser - postgres. Password is Lopeze210!.
    Currently only one database as well - robtest - a testing database till the robot is ready for production
    
    Will create functions for common queries e.g. creating/reading/updating tables.
    However the cursor object is accessible from the class instance itself, so custom queries can always be made
    using the cursor if needed
    """
    def __init__(self, DB_NAME, DB_USER, DB_PW, DB_HOST="localhost", DB_PORT="5432"):
        try:
            conn = psycopg2.connect(
                database = DB_NAME,
                user = DB_USER,
                password = DB_PW,
                host = DB_HOST,
                port = DB_PORT)
        except:
            print("Error while connecting! Ensure details you entered are correct")
        else:    
            self.cur = conn.cursor()
            print("Successfully connected to DB")
        
#     def query(self, table):
#         self.cur 
        
        
if __name__ == "__main__":
    db = DB("robtest", "postgres", "Lopeze210!")
    # db.cur.execute("your query")
