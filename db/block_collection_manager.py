from db.block import Block
from utils.common import to_object_id
from utils.db_connector import *

class BlockCollectionManager(object):
    """
    """

    @staticmethod
    def get_db_blocks(block_running_status):
        db_blocks = db.blocks.find()
        return [db_blocks]
