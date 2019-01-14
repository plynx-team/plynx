import os
import boto3
from urlparse import urlparse
from plynx.utils.remote.base import ContentsHandlerBase, RemoteBase


class ContentsHandlerS3(ContentsHandlerBase):
    def __init__(self, remote, path):
        super(ContentsHandlerS3, self).__init__(remote)
        self.path = urlparse(path).path[1:]     # get the file path in the bucket

    def get_contents_to_file(self, file_obj):
        self.remote.s3.download_fileobj(self.remote.bucket_name, self.path, file_obj)

    def set_contents_from_file(self, file_obj):
        self.remote.s3.upload_fileobj(file_obj, self.remote.bucket_name, self.path)


class RemoteS3(RemoteBase):
    def __init__(self, storage_config):
        super(RemoteS3, self).__init__(ContentsHandlerS3, storage_config)
        if self._storage_config.credential_path:
            os.environ['AWS_SHARED_CREDENTIALS_FILE'] = self._storage_config.credential_path
        parse_result = urlparse(self._storage_config.prefix)
        self.s3 = boto3.client('s3')
        self.bucket_name = parse_result.netloc
