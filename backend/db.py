import json
import config
from debug import *
import time
import mysql.connector
from mysql.connector import errorcode

class VanisherDB:
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.EnsureMySQLConnection()

    def EnsureMySQLConnection(self):
        if self.connection == None or True: #always reconnect
            try:
                Log("Trying to connect", config.DATABASE_CONFIG)
                self.connection = mysql.connector.connect(
                    host=config.DATABASE_CONFIG["host"],
                    user=config.DATABASE_CONFIG["username"],
                    password=config.DATABASE_CONFIG["password"],
                    database=config.DATABASE_CONFIG["dbname"]
                )
                Log(self.connection)
                self.cursor = self.connection.cursor()
                self.connection.autocommit = True
            except mysql.connector.errors.Error as e:
                Log(e)
        Log("Using connection", self.connection, "; Using cursor", self.cursor)

    def GetCurrentRowHeaders(self):
        return [x[0] for x in self.cursor.description]
    
    def QueryAnImage(self):
        self.EnsureMySQLConnection();
        if self.cursor == None:
            Log("Cursor is None. Aborting query and returning None")
            return None
        else:
            query = "select X.id, gt_path, mask_path from (select id, count(model_identifier) as count from images left join outputs on images.id = outputs.image_id where images.modified_time < current_timestamp - 60 group by id order by count asc, images.modified_time asc limit 1) as X inner join images where count = 0 and X.id = images.id"
            try:
                Log(query)
                self.cursor.execute(query)
                result = self.cursor.fetchall()
                if result == None or len(result) < 1:
                    Log("Couldn't find any incomplete image to dequeue. Returning None.")
                    return None
                elif len(result) > 1:
                    Log("Query returns more than 1 entries. Something's wrong. Returning None.")
                    return None
                else:
                    result = dict(zip(self.GetCurrentRowHeaders(), result[0]))
                    Log(result)
                    
                    #update modified_time
                    try:
                        id = result["id"]
                        query = "update images set modified_time = current_timestamp where id = {}".format(id)
                        self.cursor.execute(query)
                        return result
                    except mysql.connector.errors.Error as e:
                        Log("MySQL query failed. Returning None.", e)
                        return None
                    except Exception as e:
                        Log("Unknown error", e)
            except mysql.connector.errors.Error as e:
                Log("MySQL query failed. Returning None.", e)
                return None

    def GetImageStatus(self, id):
        if not id.isnumeric():
            Log("ID is invalid. Returning None")
            return '{"arraySize": 0, array: []}'

        self.EnsureMySQLConnection()
        if self.cursor == None:
            Log("Cursor is None. Aborting query and returning None")
            return '{"arraySize": 0, array: []}'
        else:
            query = "select model_identifier, out_path, unix_timestamp(processed_time) as processed_time, unix_timestamp(completed_time) as completed_time, psnr, ssim from outputs where image_id={}".format(id)
            try:
                self.cursor.execute(query)
                row_headers = self.GetCurrentRowHeaders()
                rv = self.cursor.fetchall()
                json_array=[]
                for result in rv:
                    json_array.append(dict(zip(row_headers,result)))
                json_data = {}
                json_data ["arraySize"] = len(rv)
                json_data ["array"] = json_array
                return json.dumps(json_data)
            except mysql.connector.Error as e:
                Log("MySQL query failed. Returning None.", e)
                return '{"arraySize": 0, array: []}'

    def QueueAnImage(self, gt_path, mask_path, ip, agent):
        self.EnsureMySQLConnection();
        if self.cursor == None:
            Log("Cursor is None. Aborting enqueueing and returning -1")
            return -1
        else:
            query = "Insert into images values(null, '{}', '{}', current_timestamp, '1970-01-01 00:00:01', '{}', '{}')".format(gt_path, mask_path, ip, agent)
            try:
                Log(query)
                self.cursor.execute(query)
                return self.cursor.lastrowid
            except mysql.connector.errors.Error as e:
                Log("MySQL query failed. Returning -1.", e)
                return -1
    
    def CompleteAnImage(self, id, inserted_images):
        self.EnsureMySQLConnection();
        if self.cursor == None:
            Log("Cursor is None. Aborting enqueueing and returning False")
            return False
        else:
            Log("len(inserted_images) =", len(inserted_images))
            value_query = ""
            for i in range(0, len(inserted_images)):
                model_identifier = inserted_images[i][0]
                outName = inserted_images[i][1]
                psnr = inserted_images[i][2]
                ssim = inserted_images[i][3]
                if i > 0: value_query += ", "
                value_query += "({}, '{}', '{}', current_timestamp, null, {}, {}, -1)".format(id, model_identifier, outName, psnr, ssim)
            query = "insert into outputs values " + value_query
            try:
                Log("complete Image query", query)
                self.cursor.execute(query)
                return True
            except mysql.connector.errors.Error as e:
                Log("MySQL query failed. Returning False.", e)
                return False
    
    def RateAnImage(self, id, model_identifier, rate):
        rate = min(max(rate, 0), 5)
        self.EnsureMySQLConnection();
        if self.cursor == None:
            Log("Cursor is None. Aborting enqueueing and returning False")
            return False
        else:
            query = "Update outputs set rate = {} where image_id = {} and model_identifier = '{}'".format(rate, id, model_identifier)
            try:
                Log(query)
                self.cursor.execute(query)
                return True
            except mysql.connector.errors.Error as e:
                Log("MySQL query failed. Returning False.", e)
                return False

if __name__ == "__main__":
    db = VanisherDB()
    print(db.QueryAnImage())


