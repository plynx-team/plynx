#!/usr/bin/env python
import json
from db import BlockCollectionManager
from web.common import app, request
from utils.common import to_object_id, JSONEncoder

block_collection_manager = BlockCollectionManager()


@app.route('/plynx/api/v0/blocks', methods=['GET'])
@app.route('/plynx/api/v0/blocks/<block_id>', methods=['GET'])
def get_blocks(block_id=None):
    if block_id:
        return JSONEncoder().encode({
            'data': block_collection_manager.get_db_block(block_id),
            'status':'success'})
    else:
        return JSONEncoder().encode({
            'data': block_collection_manager.get_db_blocks(),
            'status':'success'})
