"""Smart file handeling"""

import uuid

import smart_open

from plynx.utils.config import get_storage_config

_GLOBAL_STORAGE_CONFIG = None


def _get_global_storage_config():
    global _GLOBAL_STORAGE_CONFIG   # pylint: disable=global-statement
    if not _GLOBAL_STORAGE_CONFIG:
        _GLOBAL_STORAGE_CONFIG = get_storage_config()
    return _GLOBAL_STORAGE_CONFIG


def open(file, mode="rt"):  # pylint: disable=redefined-builtin
    """Open file using internal configuration"""
    file = f"{_get_global_storage_config().prefix}{file}"
    return smart_open.open(file, mode)


def get_file_stream(file_path, preview=False, file_type=None):  # pylint: disable=unused-argument
    """Get file stream object (deprecated)"""
    # TODO: remove this function
    return open(file_path, "rb")


def upload_file_stream(fp, file_path=None, seek=True):  # pylint: disable=invalid-name
    """Upload file stream to a given path (deprecated)"""
    # TODO: remove this function
    if seek:
        fp.seek(0)
    if file_path is None:
        file_path = str(uuid.uuid1())
    with open(file_path, "wb") as fo:   # pylint: disable=invalid-name
        fo.write(fp.read())
    return file_path
