#!/usr/bin/env python
import json
from db import BlockCollectionManager
from web.common import app, request
from utils.common import to_object_id, JSONEncoder

block_collection_manager = BlockCollectionManager()


@app.route('/plynx/api/v0/blocks', methods=['GET'])
def get_blocks():
    return JSONEncoder().encode({
        'data': block_collection_manager.get_db_blocks(),
        'status':'success'})
