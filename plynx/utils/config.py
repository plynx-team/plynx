import logging
import yaml
import os
from collections import namedtuple

PLYNX_CONFIG_PATH = os.getenv('PLYNX_CONFIG_PATH', 'config.yaml')
_config = None

MasterConfig = namedtuple('MasterConfig', 'internal_host host port')
WorkerConfig = namedtuple('WorkerConfig', 'user')
MongoConfig = namedtuple('MongoConfig', 'user password host port')
StorageConfig = namedtuple('StorageConfig', 'scheme prefix credential_path')
AuthConfig = namedtuple('AuthConfig', 'secret_key')
WebConfig = namedtuple('WebConfig', 'host port endpoint debug')
DemoConfig = namedtuple('DemoConfig', 'enabled, graph_ids')
CloudServiceConfig = namedtuple('CloudServiceConfig', 'prefix')

Config = namedtuple(
    'Config',
    [
        'master',
        'worker',
        'db',
        'storage',
        'auth',
        'web',
        'demo',
        'cloud_service',
    ]
)


def __init__():
    global _config
    if os.path.exists(PLYNX_CONFIG_PATH):
        with open(PLYNX_CONFIG_PATH) as f:
            logging.critical('Using config `{}`'.format(PLYNX_CONFIG_PATH))
            _config = yaml.safe_load(f)
    else:
        logging.critical('PLYNX_CONFIG_PATH `{}` is not found'.format(PLYNX_CONFIG_PATH))
        _config = {}


def get_master_config():
    return MasterConfig(
        internal_host=_config.get('master', {}).get('internal_host', '0.0.0.0'),
        host=_config.get('master', {}).get('host', '127.0.0.1'),
        port=int(_config.get('master', {}).get('port', 17011)),
    )


def get_worker_config():
    return WorkerConfig(
        user=_config.get('worker', {}).get('user', ''),
    )


def get_db_config():
    return MongoConfig(
        user=_config.get('mongodb', {}).get('user', ''),
        password=_config.get('mongodb', {}).get('password', ''),
        host=_config.get('mongodb', {}).get('host', '127.0.0.1'),
        port=int(_config.get('mongodb', {}).get('port', 27017))
    )


def get_storage_config():
    return StorageConfig(
        scheme=_config.get('storage', {}).get('scheme', 'file'),
        prefix=_config.get('storage', {}).get(
            'prefix',
            os.path.join(os.path.expanduser("~"), 'plynx', 'data')
        ),
        credential_path=_config.get('storage', {}).get('credential_path', None),
    )


def get_auth_config():
    return AuthConfig(
        secret_key=_config.get('auth', {}).get('secret_key', '') or '',
    )


def get_web_config():
    return WebConfig(
        host=_config.get('web', {}).get('host', '0.0.0.0'),
        port=int(_config.get('web', {}).get('port', 5000)),
        endpoint=_config.get('web', {}).get('endpoint', 'http://127.0.0.1:3000'),
        debug=bool(_config.get('web', {}).get('debug', False)),
    )


def get_demo_config():
    return DemoConfig(
        enabled=_config.get('demo', {}).get('enabled', False),
        graph_ids=_config.get('demo', {}).get('graph_ids', []),
    )


def get_cloud_service_config():
    return CloudServiceConfig(
        prefix=_config.get('cloud_service', {}).get('prefix', 'gs://sample'),
    )


def get_config():
    return Config(
        master=get_master_config(),
        worker=get_worker_config(),
        db=get_db_config(),
        storage=get_storage_config(),
        auth=get_auth_config(),
        web=get_web_config(),
        demo=get_demo_config(),
        cloud_service=get_cloud_service_config(),
    )


def set_parameter(levels, value):
    """Set global config parameter

    Args:
        levels  (list):     List of levels, i.e. ['mongodb', 'user']
        value   (value):    Value of the parameter
    """
    sublevel = _config
    for level in levels[:-1]:
        if level not in sublevel:
            sublevel[level] = {}
        sublevel = sublevel[level]
    sublevel[levels[-1]] = value


__init__()
