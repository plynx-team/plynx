import json
from flask import request, send_file, g
from plynx.graph.base_nodes.file import File as FileNodeClass
from plynx.plugins.resources import File as FileCls
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors
from plynx.plugins.base import PreviewObject
from plynx.plugins.managers import resource_manager
from plynx.utils.common import JSONEncoder
from plynx.utils.file_handler import get_file_stream, upload_file_stream
from plynx.constants import ResourcePostStatus

RESOURCE_TYPES = set(resource_manager.resources_dict)


@app.route('/plynx/api/v0/resource/<resource_id>', methods=['GET'])
@handle_errors
def get_resource(resource_id):
    preview = json.loads(request.args.get('preview', 'false'))
    file_type = request.args.get('file_type', None)
    if preview and not file_type:
        return make_fail_response('In preview mode `file_type` must be specified'), 400
    fp = get_file_stream(resource_id, preview=preview, file_type=file_type)
    if preview:
        preview_object = PreviewObject(
            fp=fp,
            resource_id=resource_id,
        )
        return resource_manager[file_type].preview(preview_object)
    return send_file(
        fp,
        attachment_filename=resource_id)


@app.route('/plynx/api/v0/resource', methods=['POST'])
@handle_errors
@requires_auth
def post_resource():
    resource_id = upload_file_stream(request.files['data'])
    return JSONEncoder().encode({
        'status': ResourcePostStatus.SUCCESS,
        'resource_id': resource_id
    })


@app.route('/plynx/api/v0/upload_file', methods=['POST', 'PUT'])
@handle_errors
@requires_auth
def upload_file():
    assert len(request.files) == 1
    title = request.form.get('title', '{title}')
    description = request.form.get('description', '{description}')
    file_type = request.form.get('file_type', FileCls.NAME)
    if file_type not in RESOURCE_TYPES:
        return make_fail_response('Unknown file type `{}`'.format(file_type)), 400

    resource_id = upload_file_stream(request.files['data'])
    file = FileNodeClass.get_default()
    file.author = g.user._id
    file.title = title
    file.description = description
    file.outputs[0].resource_id = resource_id
    file.outputs[0].file_type = file_type
    file.save()

    return JSONEncoder().encode({
        'status': ResourcePostStatus.SUCCESS,
        'resource_id': resource_id,
        'node': file.to_dict(),
    })
