#!/usr/bin/env python
from __future__ import absolute_import
import json
from db import File, FileCollectionManager
from web.common import app, request, auth, g
from utils.common import to_object_id, JSONEncoder
from constants import FileStatus, FilePostAction, FilePostStatus

file_collection_manager = FileCollectionManager()


def _make_fail_response(message):
    return JSONEncoder().encode({
        'status': FilePostStatus.FAILED,
        'message': message
        })

@app.route('/plynx/api/v0/files', methods=['GET'])
@app.route('/plynx/api/v0/files/<file_id>', methods=['GET'])
@auth.login_required
def get_files(file_id=None):
    if file_id == 'new':
        return JSONEncoder().encode({
            'data': File.get_default().to_dict(),
            'status':'success'})
    elif file_id:
        file = file_collection_manager.get_db_file(file_id)
        if file:
            return JSONEncoder().encode({
                'data': file,
                'status':'success'})
        else:
            return 'File was not found', 404

    else:
        query = json.loads(request.args.get('query', "{}"))
        query["author"] = to_object_id(g.user._id)
        files_query = {k: v for k, v in query.iteritems() if k in {'per_page', 'offset', 'status', 'author'}}
        count_query = {k: v for k, v in query.iteritems() if k in {'status', 'author'}}
        return JSONEncoder().encode({
            'files': file_collection_manager.get_db_files(**files_query),
            'total_count': file_collection_manager.get_db_files_count(**count_query),
            'status':'success'})


@app.route('/plynx/api/v0/files', methods=['POST'])
@auth.login_required
def post_file():
    app.logger.debug(request.data)
    try:
        body = json.loads(request.data)['body']

        file = File()
        file.load_from_dict(body['file'])
        file.author = g.user._id

        action = body['action']
        
        if action == FilePostAction.SAVE:
            if file.file_status != FileStatus.READY:
                return _make_fail_response('File status `{}` expected. Found `{}`'.format(FileStatus.CREATED, file.file_status))
            validation_error = file.get_validation_error()
            if validation_error:
                return JSONEncoder().encode({
                            'status': FilePostStatus.VALIDATION_FAILED,
                            'message': 'File validation failed',
                            'validation_error': validation_error.to_dict()
                            })

            file.save(force=True)

        elif action == FilePostAction.VALIDATE:
            validation_error = file.get_validation_error()

            if validation_error:
                return JSONEncoder().encode({
                            'status': FilePostStatus.VALIDATION_FAILED,
                            'message': 'File validation failed',
                            'validation_error': validation_error.to_dict()
                            })
        elif action == FilePostAction.DEPRECATE:
            if file.file_status != FileStatus.READY:
                return _make_fail_response('File status `{}` expected. Found `{}`'.format(FileStatus.READY, file.file_status))

            file.file_status = FileStatus.DEPRECATED
            file.save(force=True)

        else:
            return _make_fail_response('Unknown action `{}`'.format(action))

        return JSONEncoder().encode(
            {
                'status': FilePostStatus.SUCCESS,
                'resource_id': file.outputs[0].resource_id,
                'message': 'File(_id=`{}`) successfully updated'.format(str(file._id))
            })
    except Exception as e:
        app.logger.error(e)
        return _make_fail_response('Internal error: "{}"'.format(str(e)))
