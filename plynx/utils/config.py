import logging
import yaml
import os
from collections import namedtuple

PLYNX_CONFIG_PATH = os.getenv('PLYNX_CONFIG_PATH', 'config.yaml')
_config = None

WorkerConfig = namedtuple('WorkerConfig', ['kinds'])
MongoConfig = namedtuple('MongoConfig', ['user', 'password', 'host', 'port'])
StorageConfig = namedtuple('StorageConfig', ['scheme', 'prefix', 'credential_path'])
AuthConfig = namedtuple('AuthConfig', ['secret_key'])
WebConfig = namedtuple('WebConfig', ['host', 'port', 'endpoint', 'api_endpoint', 'debug'])
DemoConfig = namedtuple('DemoConfig', ['enabled', 'kind'])
CloudServiceConfig = namedtuple('CloudServiceConfig', ['prefix', 'url_prefix', 'url_postfix'])
ResourceConfig = namedtuple('ResourceConfig', ['kind', 'title', 'cls', 'icon', 'color'])
DummyOperationConfig = namedtuple('DummyOperationConfig', ['title', 'kind', 'executor', 'operations', 'icon', 'color'])
OperationConfig = namedtuple('OperationConfig', ['kind', 'title', 'executor', 'hubs', 'resources', 'icon', 'color'])
HubConfig = namedtuple('HubConfig', ['kind', 'title', 'icon', 'cls', 'args'])
WorkflowConfig = namedtuple('WorkflowConfig', ['kind', 'title', 'executor', 'operations', 'hubs', 'icon', 'color'])
PluginsConfig = namedtuple('PluginsConfig', ['resources', 'operations', 'hubs', 'workflows', 'dummy_operations'])


Config = namedtuple(
    'Config',
    [
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


def get_worker_config():
    return WorkerConfig(
        kinds=(_config.get('worker', {}).get('kinds', [])),
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
        endpoint=_config.get('web', {}).get('endpoint', '/'),
        api_endpoint=_config.get('web', {}).get('api_endpoint', '/plynx/api/v0'),
        debug=bool(_config.get('web', {}).get('debug', False)),
    )


def get_demo_config():
    return DemoConfig(
        enabled=_config.get('demo', {}).get('enabled', False),
        kind=_config.get('demo', {}).get('kind', None),
    )


def get_cloud_service_config():
    return CloudServiceConfig(
        prefix=_config.get('cloud_service', {}).get('prefix', 'gs://sample'),
        url_prefix=_config.get('cloud_service', {}).get('url_prefix', ''),
        url_postfix=_config.get('cloud_service', {}).get('url_postfix', ''),
    )


def get_plugins():
    # resources
    kind_to_resource = {
        raw_resource['kind']: ResourceConfig(
            kind=raw_resource['kind'],
            title=raw_resource['title'],
            cls=raw_resource['cls'],
            icon=raw_resource['icon'],
            color=raw_resource.get('color', ''),
        )
        for raw_resource in _config['plugins']['resources']
    }
    # operations
    kind_to_operation = {}
    raw_operations = _config['plugins']['operations']
    unique_operation_kinds = {raw_operation['kind'] for raw_operation in raw_operations}
    for raw_operation in raw_operations:
        operation_kind = raw_operation['kind']
        sub_operation_kinds = set(raw_operation.get('operations', []))
        if len(sub_operation_kinds - unique_operation_kinds) > 0:
            raise Exception('Unknown operations: `{}`'.format(sub_operation_kinds - unique_operation_kinds))
        kind_to_operation[operation_kind] = OperationConfig(
            kind=operation_kind,
            title=raw_operation['title'],
            executor=raw_operation['executor'],
            icon=raw_operation['icon'],
            color=raw_operation['color'],
            hubs=raw_operation.get('hubs', []),
            resources=[resource for kind, resource in kind_to_resource.items() if kind in raw_operation['resources']],
        )
    # hubs
    hubs = []
    for raw_hub in _config['plugins']['hubs']:
        hubs.append(HubConfig(
            kind=raw_hub['kind'],
            title=raw_hub['title'],
            icon=raw_hub['icon'],
            cls=raw_hub['cls'],
            args=raw_hub['args'],
        ))
    # workflows
    workflows = []
    for raw_workflow in _config['plugins']['workflows']:
        sub_operation_kinds = set(raw_workflow.get('operations', []))
        if len(sub_operation_kinds - unique_operation_kinds) > 0:
            raise Exception('Unknown operations: `{}`'.format(sub_operation_kinds - unique_operation_kinds))
        workflows.append(WorkflowConfig(
            kind=raw_workflow['kind'],
            title=raw_workflow['title'],
            executor=raw_workflow['executor'],
            hubs=raw_workflow['hubs'],
            operations=list(sub_operation_kinds),
            icon='feathericons.grid',
            color='#5ed1ff',
        ))

    return PluginsConfig(
        resources=list(kind_to_resource.values()),
        operations=list(kind_to_operation.values()),
        hubs=hubs,
        workflows=workflows,
        dummy_operations=[
            DummyOperationConfig(
                title='',
                kind='dummy',
                executor='plynx.base.executor.Dummy',
                operations=[],
                icon='feathericons.grid',
                color='#5ed1ff',
                )
        ]
    )


def get_config():
    return Config(
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
