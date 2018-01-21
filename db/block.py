import copy
import datetime
import db
from . import DBObject
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import BlockRunningStatus


class Block(DBObject):
    """
    Basic block with db interface
    """

    PROPERTIES = {'inputs', 'outputs', 'parameters'}

    def __init__(self, block_id=None):
        super(Block, self).__init__()

        self._id = None
        self.title = None
        self.description = None
        self.base_block_name = None
        self.parent_block = None
        self.derived_from = None
        self.inputs = []
        self.outputs = []
        self.parameters = []
        self.logs = []
        self.block_running_status = BlockRunningStatus.CREATED
        self.x = 0
        self.y = 0

        if block_id:
            self._id = to_object_id(block_id)
            self.load()
        else:
            self._id = ObjectId()

    def to_dict(self):
        return {
                "_id": self._id,
                "base_block_name": self.base_block_name,
                "inputs": self.inputs,
                "outputs": self.outputs,
                "parameters": self.parameters,
                "logs": self.logs,
                "title": self.title,
                "description": self.description,
                "parent_block": self.parent_block,
                "derived_from": self.derived_from,
                "block_running_status": self.block_running_status.value,
                "x": self.x,
                "y": self.y
            }

    def load_from_dict(self, block_dict):
        for key, value in block_dict.iteritems():
            if key not in Block.PROPERTIES:
                setattr(self, key, value)

        self.inputs = [Input(input_dict) for input_dict in block_dict['inputs']]
        # !! Err !!

    def save(self):
        if not self.is_dirty():
            return True

        now = datetime.datetime.utcnow()

        block_dict = self.to_dict()
        block_dict["update_date"] = now

        db.blocks.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": block_dict
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self, block=None):
        if not block:
            block = db.blocks.find_one({'_id': self._id})

        self.load_from_dict(block)

        self._dirty = False

    def copy(self):
        return copy.deepcopy(self)

    def __str__(self):
        return 'Block(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'Block({})'.format(str(self.to_dict()))


if __name__ == "__main__":
    block = Block()
    block.title = 'Command 1x1'
    block.base_block_name = "command"
    block.inputs['in'] = {'type': 'file', 'value': None}
    block.outputs['out'] = {'type': 'file', 'value': None}
    block.description = 'Any command with 1 arg'
    block.parameters['text'] = {'type': 'str', 'value': ''}
    block.parameters['cmd'] = {'type': 'str', 'value': 'echo ${param[text]}'}

    print('hellow')
    exit(1)
    #block.save()

    block = Block()
    block.title = 'Echo'
    block.base_block_name = "echo"
    block.outputs['out'] = {'type': 'file', 'value': None}
    block.description = 'echo'
    block.parameters['text'] = {'type': 'str', 'value': ''}

    block.save()

    block = Block()
    block.title = 'Get Resource'
    block.base_block_name = "get_resource"
    block.outputs['out'] = {'type': 'file', 'value': None}
    block.description = 'get_resource'
    block.parameters['resource_id'] = {'type': 'str', 'value': ''}

    block.save()

    block = Block()
    block.title = 'Grep'
    block.base_block_name = "grep"
    block.inputs['in'] = {'type': 'file', 'value': None}
    block.outputs['out'] = {'type': 'file', 'value': None}
    block.description = 'grep'
    block.parameters['text'] = {'type': 'str', 'value': ''}

    block.save()
