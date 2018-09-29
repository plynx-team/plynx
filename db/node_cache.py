import copy
import datetime
from . import DBObject, Input, Output, Parameter, ParameterWidget, ValidationError
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import NodeStatus, NodeRunningStatus, FileTypes, ParameterTypes, ValidationTargetType, ValidationCode


class NodeCache(DBObject):
    """
    Basic Node Cache with db interface
    """

    PROPERTIES = {'outputs', 'logs'}
    IGNORED_PARAMETERS = {'cmd'}

    def __init__(self, node=None, graph_id=None, user_id=None):
        super(NodeCache, self).__init__()

        self._id = ObjectId()
        self.key = ''
        self.graph_id = graph_id
        self.node_id = None    # refer to Node in Graph
        self.outputs = []
        self.logs = []

        if node:
            self.node_id = node._id
            self.outputs = node.outputs
            self.logs = node.logs
            self.key = NodeCache.generate_key(node, user_id)

    def to_dict(self):
        return {
            "_id": self._id,
            "key": self.key,
            "graph_id": self.graph_id,
            "node_id": self.node_id,
            "outputs": [output.to_dict() for output in self.outputs],
            "logs": [log.to_dict() for log in self.logs]
        }

    def load_from_dict(self, node_dict):
        for key, value in node_dict.iteritems():
            if key not in NodeCache.PROPERTIES:
                setattr(self, key, value)

        self._id = to_object_id(self._id)
        self.outputs = [Output.create_from_dict(output_dict) for output_dict in node_dict['outputs']]
        self.logs = [Output.create_from_dict(logs_dict) for logs_dict in node_dict['logs']]

    def copy(self):
        node_cache = NodeCache()
        node_cache.load_from_dict(self.to_dict())
        return node_cache

    def save(self, force=False):
        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        node_cache_dict = self.to_dict()
        node_cache_dict["update_date"] = now

        db.node_cache.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": node_cache_dict
            },
            upsert=True,
        )

        self._dirty = False
        return True

    # Demo: remove user_id
    @staticmethod
    def generate_key(node, user_id):
        inputs = node.inputs
        parameters = node.parameters
        parent_node = node.parent_node

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
            for parameter in sorted_parameters if parameter.name not in NodeCache.IGNORED_PARAMETERS
        ])

        key = '{};{};{};{}'.format(parent_node, inputs_hash, parameters_hash, str(user_id))
        return key

    def __str__(self):
        return 'NodeCache(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'NodeCache({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(NodeCache, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))
