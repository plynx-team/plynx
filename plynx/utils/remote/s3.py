from future.standard_library import install_aliases
install_aliases()   # noqa

import os                                                               # noqa: E402
import boto3                                                            # noqa: E402
from botocore.errorfactory import ClientError                           # noqa: E402
from urllib.parse import urlparse                                       # noqa: E402
from plynx.utils.remote.base import ContentsHandlerBase, RemoteBase     # noqa: E402


class ContentsHandlerS3(ContentsHandlerBase):
    def __init__(self, remote, path):
        super(ContentsHandlerS3, self).__init__(remote)
        self.path = urlparse(path).path[1:]     # get the file path in the bucket

    def get_contents_to_file(self, file_obj):
        self.remote.s3.download_fileobj(Bucket=self.remote.bucket_name, Key=self.path, Fileobj=file_obj)

    def set_contents_from_file(self, file_obj):
        self.remote.s3.upload_fileobj(Fileobj=file_obj, Bucket=self.remote.bucket_name, Key=self.path)

    def remove(self):
        self.remote.s3.delete_object(Bucket=self.remote.bucket_name, Key=self.path)

    def exists(self):
        try:
            self.remote.s3.head_object(Bucket=self.remote.bucket_name, Key=self.path)
        except ClientError:
            return False
        return True


class RemoteS3(RemoteBase):
    def __init__(self, storage_config):
        super(RemoteS3, self).__init__(ContentsHandlerS3, storage_config)
        if self._storage_config.credential_path:
            os.environ['AWS_SHARED_CREDENTIALS_FILE'] = self._storage_config.credential_path
        parse_result = urlparse(self._storage_config.prefix)
        self.s3 = boto3.client('s3')
        self.bucket_name = parse_result.netloc
