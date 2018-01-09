from db.block import Block
from utils.common import to_object_id
from utils.db_connector import *

class BlockCollectionManager(object):
    """
    """

    @staticmethod
    def get_db_blocks():
        db_blocks = db.blocks.find()
        return list(db_blocks)
