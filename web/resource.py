#!/usr/bin/env python
from web.common import app, send_file
from utils.common import to_object_id, JSONEncoder
from utils.file_handler import get_file_stream


@app.route('/plynx/api/v0/resource/<resource_id>', methods=['GET'])
def get_resource(resource_id):
    return send_file(get_file_stream(resource_id), attachment_filename=resource_id)
