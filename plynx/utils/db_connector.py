import logging
import pymongo
from plynx.constants import Collections
from plynx.utils.config import get_db_config

_db = None


def init_indexes():
    _db[Collections.WORKER_STATE].create_index('insertion_date', expireAfterSeconds=5)

    _db[Collections.RUNS].create_index('insertion_date')

    _db[Collections.NODE_CACHE].create_index('key', unique=True)

    _db[Collections.TEMPLATES].create_index('insertion_date')
    _db[Collections.TEMPLATES].create_index([
        ('starred', pymongo.DESCENDING),
        ('insertion_date', pymongo.DESCENDING)
    ])
    _db[Collections.TEMPLATES].create_index([('title', pymongo.TEXT), ('description', pymongo.TEXT)])

    _db[Collections.RUNS].create_index('insertion_date')
    _db[Collections.RUNS].create_index([('title', pymongo.TEXT), ('description', pymongo.TEXT)])

    _db[Collections.USERS].create_index('username', unique=True)

    _db[Collections.RUN_CANCELLATIONS].create_index('insertion_date', expireAfterSeconds=60)
    _db[Collections.RUN_CANCELLATIONS].create_index('run_id')

    _db[Collections.GROUPS].create_index('insertion_date')
    _db[Collections.GROUPS].create_index([
        ('starred', pymongo.DESCENDING),
        ('insertion_date', pymongo.DESCENDING)
    ])
    _db[Collections.GROUPS].create_index([('title', pymongo.TEXT)])


def get_db_connector():
    global _db
    if _db:
        return _db
    connectionConfig = get_db_config()
    client = pymongo.MongoClient(connectionConfig.host, connectionConfig.port, read_preference=pymongo.read_preferences.PrimaryPreferred())
    _db = client['plynx']
    if connectionConfig.user:
        _db.authenticate(connectionConfig.user, connectionConfig.password)
    init_indexes()
    return _db


def check_connection():
    try:
        logging.info('Try db connection')
        get_db_connector().client.server_info()
    except pymongo.errors.ServerSelectionTimeoutError:
        logging.error('Connection failed')
        raise
