"""Smart file handeling"""

import uuid
from typing import BinaryIO, Optional

import smart_open

from plynx.utils.config import StorageConfig, get_storage_config

_GLOBAL_STORAGE_CONFIG: Optional[StorageConfig] = None


def _get_global_storage_config() -> StorageConfig:
    global _GLOBAL_STORAGE_CONFIG   # pylint: disable=global-statement
    if not _GLOBAL_STORAGE_CONFIG:
        _GLOBAL_STORAGE_CONFIG = get_storage_config()
    return _GLOBAL_STORAGE_CONFIG


def open(filename: str, mode: str = "rt"):  # pylint: disable=redefined-builtin
    """Open file using internal configuration"""
    cld_filename = f"{_get_global_storage_config().prefix}{filename}"
    return smart_open.open(cld_filename, mode)


def get_file_stream(file_path: str, preview: bool = False, file_type=None) -> BinaryIO:  # pylint: disable=unused-argument
    """Get file stream object (deprecated)"""
    # TODO: remove this function
    return open(file_path, "rb")


def upload_file_stream(fp: BinaryIO, file_path: Optional[str] = None, seek: bool = True) -> str:  # pylint: disable=invalid-name
    """Upload file stream to a given path (deprecated)"""
    # TODO: remove this function
    if seek:
        fp.seek(0)
    if file_path is None:
        file_path = str(uuid.uuid1())
    with open(file_path, "wb") as fo:   # pylint: disable=invalid-name
        fo.write(fp.read())
    return file_path
