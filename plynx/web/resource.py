"""All of the endpoints related to Resources"""
import json

from flask import g, request, send_file

import plynx.base.resource
import plynx.db.node
import plynx.utils.plugin_manager
from plynx.constants import NodeRunningStatus, NodeStatus
from plynx.plugins.resources.common import FILE_KIND
from plynx.utils.file_handler import get_file_stream, upload_file_stream
from plynx.utils.thumbnails import get_thumbnail
from plynx.web.common import app, handle_errors, logger, make_fail_response, make_success_response, requires_auth

RESOURCE_TYPES = list(plynx.utils.plugin_manager.get_resource_manager().kind_to_resource_class.keys())


@app.route('/plynx/api/v0/resource/<resource_id>', methods=['GET'])
@handle_errors
def get_resource(resource_id: str):
    """Get the data of the resource"""
    preview = json.loads(request.args.get('preview', 'false'))
    file_type = request.args.get('file_type', None)
    if preview and not file_type:
        return make_fail_response('In preview mode `file_type` must be specified'), 400
    file_stream = get_file_stream(resource_id, preview=preview, file_type=file_type)
    if preview:
        preview_object = plynx.base.resource.PreviewObject(
            fp=file_stream,
            resource_id=resource_id,
        )
        return plynx.utils.plugin_manager.get_resource_manager().kind_to_resource_class[file_type].preview(preview_object)
    return send_file(
        file_stream,
        download_name=resource_id
    )    # type: ignore


@app.route('/plynx/api/v0/resource', methods=['POST'])
@handle_errors
@requires_auth
def post_resource():
    """Upload a new resource"""
    resource_id = upload_file_stream(request.files['data'])
    return make_success_response({
        'resource_id': resource_id
    })


@app.route('/plynx/api/v0/upload_file', methods=['POST', 'PUT'])
@handle_errors
@requires_auth
def upload_file():
    """Upload file"""
    assert len(request.files) == 1
    title = request.form.get('title', '{title}')
    description = request.form.get('description', '{description}')
    file_type = request.form.get('file_type', FILE_KIND)
    node_kind = request.form.get('node_kind', 'basic-file')
    logger.debug(request)
    if file_type not in RESOURCE_TYPES:
        logger.debug(file_type)
        logger.debug(RESOURCE_TYPES)
        return make_fail_response(f"Unknown file type `{file_type}`"), 400

    resource_id = upload_file_stream(request.files['data'])

    file = plynx.db.node.Node(
        title=title,
        description=description,
        kind=node_kind,
        node_running_status=NodeRunningStatus.STATIC,
        node_status=NodeStatus.READY,
    )
    output = plynx.db.node.Output(
        name='file',
        file_type=file_type,
        values=[resource_id],
    )
    output.thumbnail = get_thumbnail(output)
    file.outputs.append(output)

    file.author = g.user._id
    file.save()

    return make_success_response({
        'resource_id': resource_id,
        'node': file.to_dict(),
    })
