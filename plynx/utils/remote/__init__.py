import smart_open

from plynx.utils.config import get_storage_config

_driver = None
_global_storage_config = None


def get_driver(storage_config=None):
    global _driver
    if not _driver:
        _driver = _get_driver_handler(storage_config)
    return _driver


def get_global_storage_config():
    global _global_storage_config
    if not _global_storage_config:
        _global_storage_config = get_storage_config()
    return _global_storage_config


def _get_driver_handler(storage_config=None):
    if storage_config is None:
        storage_config = get_global_storage_config()
    if storage_config.scheme == 'file':
        from plynx.utils.remote.file import RemoteFile
        return RemoteFile(storage_config)
    if storage_config.scheme == 'gs':
        from plynx.utils.remote.gs import RemoteGS
        return RemoteGS(storage_config)
    if storage_config.scheme == 's3':
        from plynx.utils.remote.s3 import RemoteS3
        return RemoteS3(storage_config)
    else:
        raise Exception('Unknown scheme `{}`'.format(storage_config.scheme))


def open(file, mode="rt"):
    file = f"{get_global_storage_config().prefix}{file}"
    return smart_open.open(file, mode)
