from future.standard_library import install_aliases
install_aliases()   # noqa

import os
from google.cloud import storage
from urllib.parse import urlparse
from plynx.utils.remote.base import ContentsHandlerBase, RemoteBase


class ContentsHandlerGS(ContentsHandlerBase):
    def __init__(self, remote, path):
        super(ContentsHandlerGS, self).__init__(remote)
        self.blob = self.remote.bucket.blob(urlparse(path).path[1:])

    def get_contents_to_file(self, file_obj):
        self.blob.download_to_file(file_obj)

    def set_contents_from_file(self, file_obj):
        self.blob.upload_from_file(file_obj)

    def remove(self):
        self.blob.delete()

    def exists(self):
        return self.blob.exists()


class RemoteGS(RemoteBase):
    def __init__(self, storage_config):
        super(RemoteGS, self).__init__(ContentsHandlerGS, storage_config)
        if self._storage_config.credential_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = self._storage_config.credential_path
        bucket_name = urlparse(self._storage_config.prefix).netloc
        client = storage.Client()
        self.bucket = client.get_bucket(bucket_name)
