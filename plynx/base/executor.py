"""Templates for PLynx Executors and utils."""

import os
import shutil
from abc import abstractmethod
from typing import Union

from plynx.constants import NodeStatus, SpecialNodeId, ValidationCode, ValidationTargetType
from plynx.db.node import Node, NodeRunningStatus, Parameter, ParameterListOfNodes, ParameterTypes
from plynx.db.validation_error import ValidationError

TMP_DIR = '/tmp/plx'


class BaseExecutor:
    """Base Executor class"""
    IS_GRAPH: bool = False

    def __init__(self, node: Node = None):
        self.node = node
        self.workdir = TMP_DIR

    @abstractmethod
    def run(self, preview: bool = False) -> str:
        """Main execution function.

        - Workdir has been initialized.
        - Inputs are not preprocessed.
        - Outputs shoul be manually postprocessed.
        - It is OK to raise an exception in this function.

        Returns:
            enum: plynx.constants.NodeRunningStatus
        """

    @abstractmethod
    def kill(self):
        """Force to kill the process.

        The reason can be the fact it was working too long or parent executor canceled it.
        """

    # pylint: disable=no-self-use
    def is_updated(self) -> bool:
        """Function that is regularly called by a Worker.

        The function is running in a separate thread and does not block execution of `run()`.

        Returns:
            (bool):     True if worker needs to update DB else False
        """
        return False

    @classmethod
    def get_default_node(cls, is_workflow: bool) -> Node:
        """Generate a new default Node for this executor"""
        node = Node()
        if cls.IS_GRAPH:
            nodes_parameter = Parameter(
                name='_nodes',
                parameter_type=ParameterTypes.LIST_NODE,
                value=ParameterListOfNodes(),
                mutable_type=False,
                publicable=False,
                removable=False,
            )
            if not is_workflow:
                # need to add inputs and outputs
                nodes_parameter.value.value.extend(
                    [
                        Node(
                            _id=SpecialNodeId.INPUT,
                            title='Input',
                            kind='dummy',
                            node_running_status=NodeRunningStatus.SPECIAL,
                            node_status=NodeStatus.READY,
                        ),
                        Node(
                            _id=SpecialNodeId.OUTPUT,
                            title='Output',
                            kind='dummy',
                            node_running_status=NodeRunningStatus.SPECIAL,
                            node_status=NodeStatus.READY,
                        ),
                    ]
                )
            node.parameters.extend([
                nodes_parameter,
            ])
            node.arrange_auto_layout()
        return node

    def init_workdir(self):
        """Make tmp dir if it does not exist"""
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)

    def clean_up(self):
        """Remove tmp dir"""
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir, ignore_errors=True)

    def validate(self) -> Union[ValidationError, None]:
        """Validate Node.

        Return:
            (ValidationError)   Validation error if found; else None
        """
        assert self.node, "Attribute `node` is not assigned"

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
            for input in self.node.inputs:  # pylint: disable=redefined-builtin
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
    """Dummy Executor. Used for static Operations"""

    def run(self, preview=False) -> str:
        """Not Implemented"""
        raise NotImplementedError()

    def status(self):
        """Not Implemented"""
        raise NotImplementedError()

    def kill(self):
        """Not Implemented"""
        raise NotImplementedError()

    @classmethod
    def get_default_node(cls, is_workflow: bool) -> Node:
        """Not Implemented"""
        raise NotImplementedError()
