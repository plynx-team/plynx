import smart_open
import uuid

from plynx.utils.config import get_storage_config

_global_storage_config = None


def get_global_storage_config():
    global _global_storage_config
    if not _global_storage_config:
        _global_storage_config = get_storage_config()
    return _global_storage_config


def open(file, mode="rt"):
    file = f"{get_global_storage_config().prefix}{file}"
    return smart_open.open(file, mode)


def get_file_stream(file_path, preview=False, file_type=None):
    return open(file_path, "rb")


def upload_file_stream(fp, file_path=None, seek=True):
    if seek:
        fp.seek(0)
    if file_path is None:
        file_path = str(uuid.uuid1())
    with open(file_path, "wb") as fo:
        fo.write(fp)
    return file_path
