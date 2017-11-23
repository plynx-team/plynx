from pymongo import MongoClient
from utils.config import GetDBConfig

connectionConfig = GetDBConfig()
client = MongoClient(connectionConfig.host, connectionConfig.port)
db = client['plynx']
if connectionConfig.user:
    db.authenticate(connectionConfig.user, connectionConfig.password)

if __name__ == '__main__':
    for p in db.pool.find():
        print(p)