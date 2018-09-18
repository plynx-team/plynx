#!/usr/bin/env python
from flask import request, send_file
from web import app, requires_auth
from utils.common import JSONEncoder
from utils.file_handler import get_file_stream, upload_file_stream
from constants import ResourcePostStatus


def _make_fail_response(message):
    return JSONEncoder().encode({
        'status': ResourcePostStatus.FAILED,
        'message': message
        })


@app.route('/plynx/api/v0/resource/<resource_id>', methods=['GET'])
def get_resource(resource_id):
    return send_file(get_file_stream(resource_id), attachment_filename=resource_id)


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
        return _make_fail_response('Internal error: "{}"'.format(str(e)))
