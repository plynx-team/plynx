import os
import shutil
from plynx.utils.remote.base import ContentsHandlerBase, RemoteBase


class ContentsHandlerFile(ContentsHandlerBase):
    def __init__(self, remote, path):
        super(ContentsHandlerFile, self).__init__(remote)
        self.path = path

    def get_contents_to_file(self, file_obj):
        with open(self.path, 'rb') as f:
            shutil.copyfileobj(f, file_obj)

    def set_contents_from_file(self, file_obj):
        with open(self.path, 'wb') as f:
            shutil.copyfileobj(file_obj, f)

    def remove(self):
        os.remove(self.path)

    def exists(self):
        return os.path.exists(self.path)


class RemoteFile(RemoteBase):
    def __init__(self, storage_config):
        super(RemoteFile, self).__init__(ContentsHandlerFile, storage_config)

        # make sure directory exists
        if not os.path.exists(self._storage_config.prefix):
            os.makedirs(self._storage_config.prefix)
