import configparser
from collections import namedtuple

CONFIG_NAME = 'db.cfg'
_config = None

MongoConfig = namedtuple('MongoConfig', 'user password host port')

def __init__():
    global _config
    _config = configparser.ConfigParser()
    _config.read(CONFIG_NAME)


def getDataPath():
    return 'image_tags'

def GetDBConfig():
    return MongoConfig(
        user=_config['MONGODB']['User'],
        password=_config['MONGODB']['Password'],
        host=_config['MONGODB']['host'],
        port=int(_config['MONGODB']['Port'])
    )

__init__()
