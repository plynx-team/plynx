import datetime
from db.db_object import DBObject
from utils.db_connector import *
from utils.common import to_object_id, ObjectId


class Block(DBObject):
    """
    Basic block with db interface
    """

    _id = None
    title = None
    description = None
    graph_id = None
    base_block_name = None
    inputs = {}
    outputs = {}
    parameters = {}

    def __init__(self, block_id=None):
        if block_id:
            self._id = to_object_id(block_id)
            self.load()

    def save(self):
        if not self.is_dirty():
            return True

        now = datetime.datetime.utcnow()

        if not self._id:
            self._id = ObjectId()

        db.blocks.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": {
                    "update_date": now,
                    "title": self.title,
                    "graph_id": self.graph_id,
                    "base_block_name": self.base_block_name,
                    "outputs": self.outputs,
                    "description": self.description,
                    "parameters": self.parameters
                },
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self):
        block = db.blocks.find_one({'_id': self._id})

        for key, value in block.iteritems():
            setattr(self, key, block[key])

        self._dirty = False


if __name__ == "__main__":
    block = Block()
    block.graph_id = ObjectId("5a28e0640310e9847ce041f0")
    block.title = 'Echo'
    block.base_block_name = "echo"
    block.outputs['out'] = ''
    block.description = 'echo'
    block.parameters['text'] = 'hello world'

    block.save()
