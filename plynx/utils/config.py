"""Global PLynx config"""
import logging
import os
from collections import namedtuple
from typing import Any, Dict, Optional

import yaml

import plynx.constants

PLYNX_CONFIG_PATH = os.getenv('PLYNX_CONFIG_PATH', 'config.yaml')
DEFAULT_ICON = 'feathericons.x-square'
DEFAULT_COLOR = '#ffffff'
_CONFIG: Optional[Dict[Any, Any]] = None

WorkerConfig = namedtuple('WorkerConfig', ['kinds'])
MongoConfig = namedtuple('MongoConfig', ['user', 'password', 'host', 'port'])
StorageConfig = namedtuple('StorageConfig', ['scheme', 'prefix', 'credential_path'])
AuthConfig = namedtuple('AuthConfig', ['secret_key'])
WebConfig = namedtuple('WebConfig', ['host', 'port', 'endpoint', 'debug'])
DemoConfig = namedtuple('DemoConfig', ['enabled', 'kind', 'template_id'])
CloudServiceConfig = namedtuple('CloudServiceConfig', ['prefix', 'url_prefix', 'url_postfix'])
ResourceConfig = namedtuple('ResourceConfig', ['kind', 'title', 'cls', 'icon', 'color'])
DummyOperationConfig = namedtuple('DummyOperationConfig', ['title', 'kind', 'executor', 'operations', 'icon', 'color'])
OperationConfig = namedtuple('OperationConfig', ['kind', 'title', 'executor', 'hubs', 'resources', 'icon', 'color', 'is_static'])
HubConfig = namedtuple('HubConfig', ['kind', 'title', 'icon', 'color', 'cls', 'args'])
WorkflowConfig = namedtuple('WorkflowConfig', ['kind', 'title', 'executor', 'operations', 'hubs', 'icon', 'color'])
PluginsConfig = namedtuple('PluginsConfig', ['resources', 'operations', 'hubs', 'workflows', 'dummy_operations'])
IAMPoliciesConfig = namedtuple('IAMPoliciesConfig', ['default_policies'])


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
        'iam_policies',
    ]
)


def __init__():
    global _CONFIG  # pylint: disable=global-statement
    if os.path.exists(PLYNX_CONFIG_PATH):
        with open(PLYNX_CONFIG_PATH) as f:
            logging.critical(f"Using config `{PLYNX_CONFIG_PATH}`")
            _CONFIG = yaml.safe_load(f)
    else:
        logging.critical(f"PLYNX_CONFIG_PATH `{PLYNX_CONFIG_PATH}` is not found")
        _CONFIG = {}


def get_worker_config():
    """Generate worker config"""
    return WorkerConfig(
        kinds=(_CONFIG.get('worker', {}).get('kinds', [])),
    )


def get_db_config():
    """Generate DB config"""
    return MongoConfig(
        user=_CONFIG.get('mongodb', {}).get('user', ''),
        password=_CONFIG.get('mongodb', {}).get('password', ''),
        host=_CONFIG.get('mongodb', {}).get('host', '127.0.0.1'),
        port=int(_CONFIG.get('mongodb', {}).get('port', 27017))
    )


def get_storage_config():
    """Generate Storage config"""
    return StorageConfig(
        scheme=_CONFIG.get('storage', {}).get('scheme', 'file'),
        prefix=_CONFIG.get('storage', {}).get(
            'prefix',
            os.path.join(os.path.expanduser("~"), 'plynx', 'data')
        ),
        credential_path=_CONFIG.get('storage', {}).get('credential_path', None),
    )


def get_auth_config():
    """Generate auth config"""
    return AuthConfig(
        secret_key=_CONFIG.get('auth', {}).get('secret_key', '') or '',
    )


def get_web_config():
    """Generate web config"""
    return WebConfig(
        host=_CONFIG.get('web', {}).get('host', '0.0.0.0'),
        port=int(_CONFIG.get('web', {}).get('port', 5005)),
        endpoint=_CONFIG.get('web', {}).get('endpoint', '/').rstrip('/'),
        debug=bool(_CONFIG.get('web', {}).get('debug', False)),
    )


def get_demo_config():
    """Generate web config"""
    return DemoConfig(
        enabled=_CONFIG.get('demo', {}).get('enabled', False),
        kind=_CONFIG.get('demo', {}).get('kind', None),
        template_id=_CONFIG.get('demo', {}).get('template_id', None),
    )


def get_cloud_service_config():
    """Generate cloud config"""
    return CloudServiceConfig(
        prefix=_CONFIG.get('cloud_service', {}).get('prefix', 'gs://sample'),
        url_prefix=_CONFIG.get('cloud_service', {}).get('url_prefix', ''),
        url_postfix=_CONFIG.get('cloud_service', {}).get('url_postfix', ''),
    )


def get_iam_policies_config():
    """Generate IAM policies config"""
    all_policies = [
        name for name, value in vars(plynx.constants.IAMPolicies).items() if not name.startswith('_')
    ]
    default_policies = set(_CONFIG.get('default_policies', all_policies))
    logging.info(f"Using default IAM policies for new users: {default_policies}")
    return IAMPoliciesConfig(
        default_policies=default_policies
    )


def get_plugins():
    """Generate kind config"""
    # resources
    kind_to_resource = {
        raw_resource['kind']: ResourceConfig(
            kind=raw_resource['kind'],
            title=raw_resource['title'],
            cls=raw_resource['cls'],
            icon=raw_resource.get('icon', DEFAULT_ICON),
            color=raw_resource.get('color', DEFAULT_COLOR),
        )
        for raw_resource in _CONFIG.get('plugins')['resources']
    }
    # operations
    kind_to_operation = {}
    raw_operations = _CONFIG.get('plugins')['operations']
    unique_operation_kinds = {raw_operation['kind'] for raw_operation in raw_operations}
    for raw_operation in raw_operations:
        operation_kind = raw_operation['kind']
        sub_operation_kinds = set(raw_operation.get('operations', []))
        if len(sub_operation_kinds - unique_operation_kinds) > 0:
            raise Exception(f"Unknown operations: `{sub_operation_kinds - unique_operation_kinds}`")
        kind_to_operation[operation_kind] = OperationConfig(
            kind=operation_kind,
            title=raw_operation['title'],
            executor=raw_operation['executor'],
            icon=raw_operation.get('icon', DEFAULT_ICON),
            color=raw_operation.get('color', DEFAULT_COLOR),
            hubs=raw_operation.get('hubs', []),
            resources=[resource for kind, resource in kind_to_resource.items() if kind in raw_operation['resources']],
            is_static=raw_operation.get('is_static', False),
        )

    # hubs
    hubs = []
    for raw_hub in _CONFIG.get('plugins')['hubs']:
        hubs.append(HubConfig(
            kind=raw_hub['kind'],
            title=raw_hub['title'],
            icon=raw_hub.get('icon', DEFAULT_ICON),
            color=raw_hub.get('color', DEFAULT_COLOR),
            cls=raw_hub['cls'],
            args=raw_hub['args'],
        ))
    # workflows
    workflows = []
    for raw_workflow in _CONFIG.get('plugins')['workflows']:
        sub_operation_kinds = set(raw_workflow.get('operations', []))
        if len(sub_operation_kinds - unique_operation_kinds) > 0:
            raise Exception(f"Unknown operations: `{sub_operation_kinds - unique_operation_kinds}`")
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
                ),
        ]
    )


def get_config():
    """Generate full config"""
    return Config(
        worker=get_worker_config(),
        db=get_db_config(),
        storage=get_storage_config(),
        auth=get_auth_config(),
        web=get_web_config(),
        demo=get_demo_config(),
        cloud_service=get_cloud_service_config(),
        iam_policies=get_iam_policies_config(),
    )


def set_parameter(levels, value):
    """Set global config parameter

    Args:
        levels  (list):     List of levels, i.e. ['mongodb', 'user']
        value   (value):    Value of the parameter
    """
    sublevel = _CONFIG
    for level in levels[:-1]:
        if level not in sublevel:   # pylint: disable=unsupported-membership-test
            sublevel[level] = {}    # pylint: disable=unsupported-assignment-operation
        sublevel = sublevel[level]  # pylint: disable=unsubscriptable-object
    sublevel[levels[-1]] = value


__init__()
