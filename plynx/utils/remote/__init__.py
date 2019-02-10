from plynx.utils.config import get_storage_config

DEFAULT_STORAGE_CONFIG = get_storage_config()


def get_driver(storage_config=None):
    if storage_config is None:
        storage_config = DEFAULT_STORAGE_CONFIG
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
