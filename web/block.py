#!/usr/bin/env python
from __future__ import absolute_import
import json
from db import Block, BlockCollectionManager
from web.common import app, request
from utils.common import to_object_id, JSONEncoder
from constants import BlockPostStatus

block_collection_manager = BlockCollectionManager()


@app.route('/plynx/api/v0/blocks', methods=['GET'])
@app.route('/plynx/api/v0/blocks/<block_id>', methods=['GET'])
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
def post_block():
    app.logger.debug(request.data)
    try:
        body = json.loads(request.data)['body']
        action = body['action']

        block = Block()
        block.load_from_dict(body['block'])
        block.save(force=True)

        return JSONEncoder().encode(
            {
                'status': BlockPostStatus.SUCCESS,
                'message': 'Block(_id=`{}`) successfully updated'.format(str(block._id))
            })
    except Exception as e:
        app.logger.error(e)
        return JSONEncoder().encode(
            {
                'status': BlockPostStatus.FAILED,
                'message': 'Internal error: "{}"'.format(str(e))
            })
