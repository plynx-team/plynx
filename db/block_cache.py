import copy
import datetime
from . import DBObject, Input, Output, Parameter, ParameterWidget, ValidationError
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import BlockStatus, BlockRunningStatus, FileTypes, ParameterTypes, ValidationTargetType, ValidationCode


class BlockCache(DBObject):
    """
    Basic block cache with db interface
    """

    PROPERTIES = {'outputs', 'logs'}
    IGNORED_PARAMETERS = {'cmd'}

    def __init__(self, block=None, graph_id=None):
        super(BlockCache, self).__init__()

        self._id = ObjectId()
        self.key = ''
        self.graph_id = graph_id
        self.block_id = None    # refer to graph's block
        self.outputs = []
        self.logs = []

        if block:
            self.block_id = block._id
            self.outputs = block.outputs
            self.logs = block.logs
            self.key = BlockCache._generate_key(
                inputs=block.inputs,
                parameters=block.parameters,
                derived_from=block.derived_from
                )

    def to_dict(self):
        return {
                "_id": self._id,
                "key": self.key,
                "graph_id": self.graph_id,
                "block_id": self.block_id,
                "outputs": [output.to_dict() for output in self.outputs],
                "logs": [log.to_dict() for log in self.logs]
            }

    def load_from_dict(self, block_dict):
        for key, value in block_dict.iteritems():
            if key not in BlockCache.PROPERTIES:
                setattr(self, key, value)

        self._id = to_object_id(self._id)
        self.outputs = [Output.create_from_dict(output_dict) for output_dict in block_dict['outputs']]
        self.logs = [Output.create_from_dict(logs_dict) for logs_dict in block_dict['logs']]

    def copy(self):
        block_cache = BlockCache()
        block_cache.load_from_dict(self.to_dict())
        return block_cache

    def save(self, force=False):
        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        block_cache_dict = self.to_dict()
        block_cache_dict["update_date"] = now

        db.block_cache.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": block_cache_dict
            },
            upsert=True,
            )

        self._dirty = False
        return True

    @staticmethod
    def _generate_key(inputs, parameters, derived_from):

        sorted_inputs = sorted(inputs, key=lambda x: x.name)
        inputs_hash = ','.join([
                '{}:{}'.format(
                    input.name,
                    ','.join(sorted(map(lambda x: x.resource_id, input.values)))
                )
                for input in sorted_inputs
            ])

        sorted_parameters = sorted(parameters, key=lambda x: x.name)
        parameters_hash = ','.join([
                '{}:{}'.format(
                    parameter.name,
                    parameter.value
                )
                for parameter in sorted_parameters if parameter.name not in BlockCache.IGNORED_PARAMETERS
            ])

        key = '{};{};{}'.format(derived_from, inputs_hash, parameters_hash)
        return key

    def __str__(self):
        return 'BlockCache(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'BlockCache({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(BlockCache, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))
