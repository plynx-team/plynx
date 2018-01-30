#!/usr/bin/env python
import json
from db import Block, BlockCollectionManager
from web.common import app, request
from utils.common import to_object_id, JSONEncoder

block_collection_manager = BlockCollectionManager()


@app.route('/plynx/api/v0/blocks', methods=['GET'])
@app.route('/plynx/api/v0/blocks/<block_id>', methods=['GET'])
def get_blocks(block_id=None):
    if block_id:
        block = block_collection_manager.get_db_block(block_id)
        if block:
            return JSONEncoder().encode({
                'data': block,
                'status':'success'})
        else:
            return 'Block was not found', 404

    else:
        return JSONEncoder().encode({
            'data': block_collection_manager.get_db_blocks(statuses=request.args.getlist('status')),
            'status':'success'})

@app.route('/plynx/api/v0/blocks/<block_id>', methods=['PUT'])
def post_block(block_id):
    print (request)
    data = json.loads(request.data)['body']

    block = Block()
    block.load_from_dict(data)

    block.save(force=True)

    return JSONEncoder().encode({'status':'success'})
