from pymongo import MongoClient
from plynx.utils.config import get_db_config

_db = None


def get_db_connector():
    global _db
    if _db:
        return _db
    connectionConfig = get_db_config()
    client = MongoClient(connectionConfig.host, connectionConfig.port)
    _db = client['plynx']
    if connectionConfig.user:
        _db.authenticate(connectionConfig.user, connectionConfig.password)
    return _db
