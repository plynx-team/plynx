import configparser
from collections import namedtuple

CONFIG_NAME = 'main.cfg'
_config = None

MongoConfig = namedtuple('MongoConfig', 'user password host port')
MasterConfig = namedtuple('MasterConfig', 'host port')

def __init__():
    global _config
    _config = configparser.ConfigParser()
    _config.read(CONFIG_NAME)


def get_db_config():
    return MongoConfig(
        user=_config['MONGODB']['User'],
        password=_config['MONGODB']['Password'],
        host=_config['MONGODB']['host'],
        port=int(_config['MONGODB']['Port'])
    )

def get_master_config():
    return MasterConfig(
        host=_config['MASTER']['host'],
        port=int(_config['MASTER']['Port'])
    )

__init__()
