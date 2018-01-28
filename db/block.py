import copy
import datetime
from . import DBObject, Input, Output, Parameter, ParameterWidget
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import BlockStatus, BlockRunningStatus, FileTypes, ParameterTypes


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
        self.block_status = BlockStatus.READY
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
                "inputs": [input.to_dict() for input in self.inputs],
                "outputs": [output.to_dict() for output in self.outputs],
                "parameters": [parameter.to_dict() for parameter in self.parameters],
                "logs": [log.to_dict() for log in self.logs],
                "title": self.title,
                "description": self.description,
                "parent_block": self.parent_block,
                "derived_from": self.derived_from,
                "block_running_status": self.block_running_status,
                "block_status": self.block_status,
                "x": self.x,
                "y": self.y
            }

    def load_from_dict(self, block_dict):
        for key, value in block_dict.iteritems():
            if key not in Block.PROPERTIES:
                setattr(self, key, value)

        self.inputs = [Input.create_from_dict(input_dict) for input_dict in block_dict['inputs']]
        self.outputs = [Output.create_from_dict(output_dict) for output_dict in block_dict['outputs']]
        self.parameters = [Parameter.create_from_dict(parameters_dict) for parameters_dict in block_dict['parameters']]
        self.logs = [Output.create_from_dict(logs_dict) for logs_dict in block_dict['logs']]

    def copy(self):
        block = Block()
        block.load_from_dict(self.to_dict())
        return block

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

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(Block, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))

    def _get_custom_element(self, arr, name):
        for parameter in arr:
            if parameter.name == name:
                return parameter
        raise Exception('Parameter "{}" not found in {}'.format(name, self.title))

    def get_input_by_name(self, name):
        return self._get_custom_element(self.inputs, name)

    def get_parameter_by_name(self, name):
        return self._get_custom_element(self.parameters, name)

    def get_output_by_name(self, name):
        return self._get_custom_element(self.outputs, name)

    def get_log_by_name(self, name):
        return self._get_custom_element(self.logs, name)


if __name__ == "__main__":
    block = Block()
    block.title = 'Command 1x1'
    block.description = 'Any command with 1 arg'
    block.base_block_name = "command"
    block.block_status = BlockStatus.READY
    block.inputs = [
        Input(
            name='in',
            file_types=[FileTypes.FILE],
            values=[])
        ]
    block.outputs = [
        Output(
            name='out',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.parameters = [
        Parameter(
            name='text',
            parameter_type=ParameterTypes.STR,
            value='hello world',
            widget=ParameterWidget(
                alias = 'text'
                )
            ),
        Parameter(
            name='cmd',
            parameter_type=ParameterTypes.STR,
            value='cat ${input[in]} | grep ${param[text]} > ${output[out]}',
            widget=ParameterWidget(
                alias = 'Command line'
                )
            )
        ]
    block.logs = [
        Output(
            name='stderr',
            file_type=FileTypes.FILE,
            resource_id=None
            ),
        Output(
            name='stdout',
            file_type=FileTypes.FILE,
            resource_id=None
            ),
        Output(
            name='worker',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.save()

    block = Block()
    block.title = 'Echo'
    block.description = 'echo bash command'
    block.base_block_name = "echo"
    block.block_status = BlockStatus.READY
    block.outputs = [
        Output(
            name='out',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.parameters = [
        Parameter(
            name='text',
            parameter_type=ParameterTypes.STR,
            value='hello world',
            widget=ParameterWidget(
                alias = 'text'
                )
            )
        ]
    block.logs = [
        Output(
            name='worker',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.save()

    block = Block()
    block.title = 'Get Resource'
    block.description = 'get_resource from DB'
    block.base_block_name = "get_resource"
    block.block_status = BlockStatus.READY
    block.outputs = [
        Output(
            name='out',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.parameters = [
        Parameter(
            name='resource_id',
            parameter_type=ParameterTypes.STR,
            value='Piton.txt',
            widget=ParameterWidget(
                alias = 'Resource ID'
                )
            )
        ]
    block.logs = [
        Output(
            name='worker',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.save()

    block = Block()
    block.title = 'Grep'
    block.description = 'grep bash command'
    block.base_block_name = "grep"
    block.block_status = BlockStatus.READY
    block.inputs = [
        Input(
            name='in',
            file_types=[FileTypes.FILE],
            values=[])
        ]
    block.outputs = [
        Output(
            name='out',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.parameters = [
        Parameter(
            name='text',
            parameter_type=ParameterTypes.STR,
            value='hello world',
            widget=ParameterWidget(
                alias = 'text'
                )
            )
        ]
    block.logs = [
        Output(
            name='worker',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.save()
