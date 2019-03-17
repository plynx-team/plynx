#!/usr/bin/env python
import json
from flask import request, send_file
from plynx.web import app, requires_auth, make_fail_response
from plynx.utils.common import JSONEncoder
from plynx.utils.file_handler import get_file_stream, upload_file_stream
from plynx.constants import ResourcePostStatus


@app.route('/plynx/api/v0/resource/<resource_id>', methods=['GET'])
def get_resource(resource_id):
    preview = json.loads(request.args.get('preview', 'false'))
    file_type = request.args.get('file_type', None)
    return send_file(
        get_file_stream(resource_id, preview=preview, file_type=file_type),
        attachment_filename=resource_id)


@app.route('/plynx/api/v0/resource', methods=['POST'])
@requires_auth
def post_resource():
    try:
        resource_id = upload_file_stream(request.files['data'])
        return JSONEncoder().encode({
            'status': ResourcePostStatus.SUCCESS,
            'resource_id': resource_id
        })
    except Exception as e:
        app.logger.error(e)
        return make_fail_response('Internal error: "{}"'.format(str(e)))
