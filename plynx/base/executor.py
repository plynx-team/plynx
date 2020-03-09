import os
import shutil
from abc import abstractmethod
from plynx.db.node import Node, Parameter, ParameterTypes, NodeRunningStatus
from plynx.db.validation_error import ValidationError
from plynx.constants import NodeStatus, SpecialNodeId, ValidationTargetType, ValidationCode

TMP_DIR = '/tmp/plx'


class BaseExecutor:
    IS_GRAPH = False

    def __init__(self, node):
        self.node = node
        self.workdir = TMP_DIR

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def status(self):
        pass

    @abstractmethod
    def kill(self):
        pass

    @classmethod
    def get_default_node(cls, is_workflow):
        node = Node()
        if cls.IS_GRAPH:
            nodes_parameter = Parameter.from_dict({
                'name': '_nodes',
                'parameter_type': ParameterTypes.LIST_NODE,
                'value': [],
                'mutable_type': False,
                'publicable': False,
                'removable': False,
                }
            )
            if not is_workflow:
                # need to add inputs and outputs
                import logging
                logging.info(type(nodes_parameter.value.value), 'a')
                nodes_parameter.value.value.extend(
                    [
                        Node.from_dict({
                            '_id': SpecialNodeId.INPUT,
                            'title': 'Input',
                            'description': 'Operation inputs',
                            'node_running_status': NodeRunningStatus.SPECIAL,
                            'node_status': NodeStatus.READY,
                        }),
                        Node.from_dict({
                            '_id': SpecialNodeId.OUTPUT,
                            'title': 'Output',
                            'description': 'Operation outputs',
                            'node_running_status': NodeRunningStatus.SPECIAL,
                            'node_status': NodeStatus.READY,
                        }),
                    ]
                )
            node.parameters.extend([
                nodes_parameter,
            ])
            node.arrange_auto_layout()
        return node

    def init_workdir(self):
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)

    def clean_up(self):
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir, ignore_errors=True)

    def validate(self):
        """Validate Node.

        Return:
            (ValidationError)   Validation error if found; else None
        """
        violations = []
        if self.node.title == '':
            violations.append(
                ValidationError(
                    target=ValidationTargetType.PROPERTY,
                    object_id='title',
                    validation_code=ValidationCode.MISSING_PARAMETER
                ))

        # Meaning the node is in the graph. Otherwise souldn't be in validation step
        if self.node.node_status != NodeStatus.CREATED:
            for input in self.node.inputs:
                min_count = input.min_count if input.is_array else 1
                if len(input.input_references) < min_count:
                    violations.append(
                        ValidationError(
                            target=ValidationTargetType.INPUT,
                            object_id=input.name,
                            validation_code=ValidationCode.MISSING_INPUT
                        ))

            if self.node.node_status == NodeStatus.MANDATORY_DEPRECATED:
                violations.append(
                    ValidationError(
                        target=ValidationTargetType.NODE,
                        object_id=str(self.node._id),
                        validation_code=ValidationCode.DEPRECATED_NODE
                    ))

        if len(violations) == 0:
            return None

        return ValidationError(
            target=ValidationTargetType.NODE,
            object_id=str(self.node._id),
            validation_code=ValidationCode.IN_DEPENDENTS,
            children=violations
        )


class Dummy(BaseExecutor):
    def __init__(self, node=None):
        super(Dummy, self).__init__(node)

    def run(self):
        raise NotImplementedError()

    def status(self):
        raise NotImplementedError()

    def kill(self):
        raise NotImplementedError()

    @classmethod
    def get_default_node(cls, is_workflow):
        raise NotImplementedError()
