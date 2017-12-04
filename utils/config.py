from collections import namedtuple
import yaml

CONFIG_NAME = 'config.yaml'
_config = None

MongoConfig = namedtuple('MongoConfig', 'user password host port')
MasterConfig = namedtuple('MasterConfig', 'host port')

def __init__():
    global _config
    with open(CONFIG_NAME) as f:
        _config = yaml.safe_load(f)
    print _config


def get_db_config():
    return MongoConfig(
        user=_config['mongodb']['user'],
        password=_config['mongodb']['password'],
        host=_config['mongodb']['host'],
        port=int(_config['mongodb']['port'])
    )

def get_master_config():
    return MasterConfig(
        host=_config['master']['host'],
        port=int(_config['master']['port'])
    )

__init__()
