import copy
import datetime
from . import DBObject, Input, Output, Parameter, ParameterWidget, ValidationError
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import NodeStatus, NodeRunningStatus, FileTypes, ParameterTypes, ValidationTargetType, ValidationCode


class Node(DBObject):
    """
    Basic Node with db interface
    """

    PROPERTIES = {'inputs', 'outputs', 'parameters'}

    def __init__(self, node_id=None):
        super(Node, self).__init__()

        self._id = None
        self.title = None
        self.description = None
        self.base_node_name = None
        self.parent_node = None
        self.inputs = []
        self.outputs = []
        self.parameters = []
        self.logs = []
        self.node_running_status = NodeRunningStatus.CREATED
        self.node_status = NodeStatus.READY
        self.cache_url = None
        self.x = 0
        self.y = 0
        self.author = None
        self.public = False

        if node_id:
            self._id = to_object_id(node_id)
            self.load()
        else:
            self._id = ObjectId()

    def to_dict(self):
        return {
                "_id": self._id,
                "_type": self._type,
                "base_node_name": self.base_node_name,
                "inputs": [input.to_dict() for input in self.inputs],
                "outputs": [output.to_dict() for output in self.outputs],
                "parameters": [parameter.to_dict() for parameter in self.parameters],
                "logs": [log.to_dict() for log in self.logs],
                "title": self.title,
                "description": self.description,
                "parent_node": self.parent_node,
                "node_running_status": self.node_running_status,
                "node_status": self.node_status,
                "cache_url": self.cache_url,
                "x": self.x,
                "y": self.y,
                "author": self.author,
                "public": self.public
            }

    def load_from_dict(self, node_dict):
        for key, value in node_dict.iteritems():
            if key not in Node.PROPERTIES:
                setattr(self, key, value)

        self._id = to_object_id(self._id)
        self.author = to_object_id(self.author)

        self.inputs = [Input.create_from_dict(input_dict) for input_dict in node_dict['inputs']]
        self.outputs = [Output.create_from_dict(output_dict) for output_dict in node_dict['outputs']]
        self.parameters = [Parameter.create_from_dict(parameters_dict) for parameters_dict in node_dict['parameters']]
        self.logs = [Output.create_from_dict(logs_dict) for logs_dict in node_dict['logs']]

    def copy(self):
        node = Node()
        node.load_from_dict(self.to_dict())
        return node

    def save(self, force=False):
        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        node_dict = self.to_dict()
        node_dict["update_date"] = now

        db.nodes.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": node_dict
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self, node=None):
        if not node:
            node = db.nodes.find_one({'_id': self._id})

        self.load_from_dict(node)

        self._dirty = False

    def copy(self):
        return copy.deepcopy(self)

    def get_validation_error(self):
        """Return validation error if found; else None"""
        violations = []
        if self.title == '':
            violations.append(
                ValidationError(
                    target=ValidationTargetType.PROPERTY,
                    object_id='title',
                    validation_code=ValidationCode.MISSING_PARAMETER
                ))

        for input in self.inputs:
            if input.min_count < 0:
                violations.append(
                    ValidationError(
                        target=ValidationTargetType.INPUT,
                        object_id=input.name,
                        validation_code=ValidationCode.MINIMUM_COUNT_MUST_NOT_BE_NEGATIVE
                    ))
            if input.min_count > input.max_count and input.max_count > 0:
                violations.append(
                    ValidationError(
                        target=ValidationTargetType.INPUT,
                        object_id=input.name,
                        validation_code=ValidationCode.MINIMUM_COUNT_MUST_BE_GREATER_THAN_MAXIMUM
                    ))
            if input.max_count == 0:
                violations.append(
                    ValidationError(
                        target=ValidationTargetType.INPUT,
                        object_id=input.name,
                        validation_code=ValidationCode.MAXIMUM_COUNT_MUST_NOT_BE_ZERO
                    ))

        # Meaning the node is in the graph. Otherwise souldn't be in validation step
        if self.node_status != NodeStatus.CREATED:
            for input in self.inputs:
                if len(input.values) < input.min_count:
                    violations.append(
                        ValidationError(
                            target=ValidationTargetType.INPUT,
                            object_id=input.name,
                            validation_code=ValidationCode.MISSING_INPUT
                        ))

        if len(violations) == 0:
            return None

        return ValidationError(
                    target=ValidationTargetType.NODE,
                    object_id=str(self._id),
                    validation_code=ValidationCode.IN_DEPENDENTS,
                    children=violations
                    )

    def __str__(self):
        return 'Node(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'Node({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(Node, self).__getattr__(name)
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

    @staticmethod
    def get_default(base_node_name):
        block = Block()
        block.title = ''
        block.description = ''
        block.base_block_name = "command"
        block.block_status = BlockStatus.CREATED
        block.public = False
        block.parameters = [
            Parameter(
                name='cmd',
                parameter_type=ParameterTypes.TEXT,
                value='bash -c " "',
                mutable_type=False,
                publicable=False,
                removable=False
                ),
            Parameter(
                name='cacheable',
                parameter_type=ParameterTypes.BOOL,
                value=True,
                mutable_type=False,
                publicable=False,
                removable=False
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
        return node
