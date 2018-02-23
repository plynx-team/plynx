#!/usr/bin/env python
from __future__ import absolute_import
import json
from db import Block, BlockCollectionManager
from web.common import app, request, auth
from utils.common import to_object_id, JSONEncoder
from constants import BlockStatus, BlockPostAction, BlockPostStatus

block_collection_manager = BlockCollectionManager()


def _make_fail_response(message):
    return JSONEncoder().encode({
        'status': BlockPostStatus.FAILED,
        'message': message
        })

@app.route('/plynx/api/v0/blocks', methods=['GET'])
@app.route('/plynx/api/v0/blocks/<block_id>', methods=['GET'])
@auth.login_required
def get_blocks(block_id=None):
    if block_id == 'new':
        return JSONEncoder().encode({
            'data': Block.get_default().to_dict(),
            'status':'success'})
    elif block_id:
        block = block_collection_manager.get_db_block(block_id)
        if block:
            return JSONEncoder().encode({
                'data': block,
                'status':'success'})
        else:
            return 'Block was not found', 404

    else:
        query = json.loads(request.args.get('query', "{}"))
        status = query['status'] if query and 'status' in query else []
        return JSONEncoder().encode({
            'data': block_collection_manager.get_db_blocks(status=status),
            'status':'success'})


@app.route('/plynx/api/v0/blocks', methods=['POST'])
@auth.login_required
def post_block():
    app.logger.debug(request.data)
    try:
        body = json.loads(request.data)['body']

        block = Block()
        block.load_from_dict(body['block'])

        action = body['action']
        if action == BlockPostAction.SAVE:
            if block.block_status != BlockStatus.CREATED:
                return _make_fail_response('Cannot save block with status `{}`'.format(block.block_status))

            block.save(force=True)

        elif action == BlockPostAction.APPROVE:
            if block.block_status != BlockStatus.CREATED:
                return _make_fail_response('Block status `{}` expected. Found `{}`'.format(BlockStatus.CREATED, block.block_status))
            validation_error = block.get_validation_error()
            if validation_error:
                return JSONEncoder().encode({
                            'status': BlockPostStatus.VALIDATION_FAILED,
                            'message': 'Block validation failed',
                            'validation_error': validation_error.to_dict()
                            })

            block.block_status = BlockStatus.READY
            block.save(force=True)

        elif action == BlockPostAction.VALIDATE:
            validation_error = block.get_validation_error()

            if validation_error:
                return JSONEncoder().encode({
                            'status': BlockPostStatus.VALIDATION_FAILED,
                            'message': 'Block validation failed',
                            'validation_error': validation_error.to_dict()
                            })
        elif action == BlockPostAction.DEPRECATE:
            if block.block_status != BlockStatus.READY:
                return _make_fail_response('Block status `{}` expected. Found `{}`'.format(BlockStatus.READY, block.block_status))

            block.block_status = BlockStatus.DEPRECATED
            block.save(force=True)

        else:
            return _make_fail_response('Unknown action `{}`'.format(action))

        return JSONEncoder().encode(
            {
                'status': BlockPostStatus.SUCCESS,
                'message': 'Block(_id=`{}`) successfully updated'.format(str(block._id))
            })
    except Exception as e:
        app.logger.error(e)
        return _make_fail_response('Internal error: "{}"'.format(str(e)))
