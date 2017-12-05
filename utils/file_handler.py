import io
from boto import storage_uri

SCHEME = 'gs'

def get_file_stream(file_path):
    content = storage_uri(file_path, SCHEME)
    content_stream = io.BytesIO()
    content.get_contents_to_file(content_stream)
    content_stream.seek(0)
    return content_stream

def upload_file_stream(file_path, fp):
    content = storage_uri(file_path, SCHEME)
    content.set_contents_from_file(fp)


if __name__ == '__main__':
    with open('/tmp/a') as fp:
        upload_file_stream('image_tags/tmp/a', fp)
