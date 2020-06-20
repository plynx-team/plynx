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
        """Main execution function.

        - Workdir has been initialized.
        - Inputs are not preprocessed.
        - Outputs shoul be manually postprocessed.
        - It is OK to raise an exception in this function.

        Returns:
            enum: plynx.constants.NodeRunningStatus
        """
        pass

    @abstractmethod
    def status(self):
        """No currently used.
        """
        pass

    @abstractmethod
    def kill(self):
        """Force to kill the process.

        The reason can be the fact it was working too long or parent executor canceled it.
        """
        pass

    def is_updated(self):
        """Function that is regularly called by a Worker.

        The function is running in a separate thread and does not block execution of `run()`.

        Returns:
            (bool):     True if worker needs to update DB else False
        """
        return False

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
                nodes_parameter.value.value.extend(
                    [
                        Node.from_dict({
                            '_id': SpecialNodeId.INPUT,
                            'title': 'Input',
                            'kind': 'dummy',
                            'node_running_status': NodeRunningStatus.SPECIAL,
                            'node_status': NodeStatus.READY,
                        }),
                        Node.from_dict({
                            '_id': SpecialNodeId.OUTPUT,
                            'title': 'Output',
                            'kind': 'dummy',
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
