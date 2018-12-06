from pymongo import MongoClient, TEXT
from plynx.constants import Collections
from plynx.utils.config import get_db_config

_db = None


def init_indexes():
    existing_collections = _db.collection_names()

    if Collections.MASTER_STATE not in existing_collections:
        _db.create_collection(Collections.MASTER_STATE, capped=True, size=16777216, max=1)

    _db[Collections.GRAPHS].create_index('insertion_date')
    _db[Collections.GRAPHS].create_index('update_date')
    _db[Collections.GRAPHS].create_index([('title', TEXT), ('description', TEXT)])

    _db[Collections.NODE_CACHE].create_index('key', unique=True)

    _db[Collections.NODES].create_index([('title', TEXT), ('description', TEXT)])

    _db[Collections.USERS].create_index('username', unique=True)


def get_db_connector():
    global _db
    if _db:
        return _db
    connectionConfig = get_db_config()
    client = MongoClient(connectionConfig.host, connectionConfig.port)
    _db = client['plynx']
    if connectionConfig.user:
        _db.authenticate(connectionConfig.user, connectionConfig.password)
    init_indexes()
    return _db
