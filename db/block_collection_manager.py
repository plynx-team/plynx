from . import Block
from utils.common import to_object_id
from utils.db_connector import *

class BlockCollectionManager(object):
    """
    """

    @staticmethod
    def get_db_blocks():
        db_blocks = db.blocks.find({}).sort('insertion_date', -1)
        return list(db_blocks)

    @staticmethod
    def get_db_block(block_id):
        return db.blocks.find_one({'_id': to_object_id(block_id)})
