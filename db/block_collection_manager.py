from . import Block
from utils.common import to_object_id
from utils.db_connector import *


class BlockCollectionManager(object):
    """
    """

    @staticmethod
    def get_db_blocks(author, status=None, per_page=20, offset=0):
        if status and isinstance(status, basestring):
            status = [status]
        if not status:
            db_blocks = db.blocks.find({
                '$or': [
                    {'author': author},
                    {'public': True}
                ]
                }).sort('insertion_date', -1).skip(offset).limit(per_page)
        else:
            db_blocks = db.blocks.find({
                '$and': [{
                    '$or': [
                            {'author': author},
                            {'public': True}
                        ]
                    },
                    {'block_status': {'$in': status}}
                    ]
                }).sort('insertion_date', -1).skip(offset).limit(per_page)

        res = []
        for block in db_blocks:
            block['_readonly'] = (author != to_object_id(block['author']))
            res.append(block)
        return res

    @staticmethod
    def get_db_blocks_by_ids(ids):
        db_blocks = db.blocks.find({
            '_id': {
                '$in': list(ids)
                }
            })

        return list(db_blocks)

    @staticmethod
    def get_db_blocks_count(author, status=None):
        if status and isinstance(status, basestring):
            status = [status]
        if not status:
            return db.blocks.count({
                '$or': [
                    {'author': author},
                    {'public': True}
                ]
                })
        else:
            return db.blocks.count({
                '$and': [{
                    '$or': [
                            {'author': author},
                            {'public': True}
                        ]
                    },
                    {'block_status': {'$in': status}}
                    ]
                })

    @staticmethod
    def get_db_block(block_id, author):
        res = db.blocks.find_one({'_id': to_object_id(block_id)})
        res['_readonly'] = (author != to_object_id(res['author']))
        return res
