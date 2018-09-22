from collections import namedtuple
import yaml

CONFIG_NAME = 'config.yaml'
_config = None

MasterConfig = namedtuple('MasterConfig', 'host port')
MongoConfig = namedtuple('MongoConfig', 'user password host port')
StorageConfig = namedtuple('StorageConfig', 'scheme resources stderr stdout worker')
AuthConfig = namedtuple('AuthConfig', 'secret_key')
WebConfig = namedtuple('WebConfig', 'endpoint')
DemoConfig = namedtuple('DemoConfig', 'graph_ids')


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

def get_storage_config():
    return StorageConfig(
        scheme=_config['storage']['scheme'],
        resources=_config['storage']['resources'],
        stderr=_config['storage']['stderr'],
        stdout=_config['storage']['stdout'],
        worker=_config['storage']['worker']
    )

def get_auth_config():
    return AuthConfig(
        secret_key=_config['auth']['secret_key']
        )

def get_web_config():
    return WebConfig(
        endpoint=_config['web']['endpoint']
        )

def get_demo_config():
    return DemoConfig(
        graph_ids=_config['demo']['graph_ids'] or []
        )

__init__()
