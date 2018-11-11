import io
import uuid
from boto import storage_uri
from plynx.utils.config import get_storage_config

STORAGE_CONFIG = get_storage_config()


def get_file_stream(file_path, prefix=None, preview=False):
    if prefix is None:
        prefix = STORAGE_CONFIG.resources
    content = storage_uri(prefix + file_path, STORAGE_CONFIG.scheme)
    content_stream = io.BytesIO()
    content.get_contents_to_file(content_stream)
    content_stream.seek(0)
    if preview:
        content_stream.truncate(1024 * 1024)
    return content_stream


def upload_file_stream(fp, prefix=None, file_path=None, seek=True):
    if seek:
        fp.seek(0)
    if file_path is None:
        file_path = str(uuid.uuid1())
    if prefix is None:
        prefix = STORAGE_CONFIG.resources
    content = storage_uri(STORAGE_CONFIG.resources + file_path, STORAGE_CONFIG.scheme)
    content.new_key().set_contents_from_file(fp)
    return file_path


if __name__ == '__main__':
    with open('/tmp/a') as fp:
        upload_file_stream('plynx/tmp/a', fp)
