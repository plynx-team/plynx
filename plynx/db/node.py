from plynx.constants import Collections
from plynx.db import DBObject, DBObjectField, Input, Output, Parameter, ValidationError
from plynx.utils.common import ObjectId
from plynx.constants import NodeStatus, NodeRunningStatus, ValidationTargetType, ValidationCode


class Node(DBObject):
    """Basic Node with db interface."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        'title': DBObjectField(
            type=str,
            default='Title',
            is_list=False,
            ),
        'description': DBObjectField(
            type=str,
            default='Description',
            is_list=False,
            ),
        'base_node_name': DBObjectField(
            type=str,
            default='bash_jinja2',
            is_list=False,
            ),
        'parent_node': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'successor_node': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'inputs': DBObjectField(
            type=Input,
            default=list,
            is_list=True,
            ),
        'outputs': DBObjectField(
            type=Output,
            default=list,
            is_list=True,
            ),
        'parameters': DBObjectField(
            type=Parameter,
            default=list,
            is_list=True,
            ),
        'logs': DBObjectField(
            type=Output,
            default=list,
            is_list=True,
            ),
        'node_running_status': DBObjectField(
            type=str,
            default=NodeRunningStatus.CREATED,
            is_list=False,
            ),
        'node_status': DBObjectField(
            type=str,
            default=NodeStatus.CREATED,
            is_list=False,
            ),
        'cache_url': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'x': DBObjectField(
            type=int,
            default=0,
            is_list=False,
            ),
        'y': DBObjectField(
            type=int,
            default=0,
            is_list=False,
            ),
        'author': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'starred': DBObjectField(
            type=bool,
            default=False,
            is_list=False,
            ),
    }

    DB_COLLECTION = Collections.NODES

    def get_validation_error(self):
        """Validate Node.

        Return:
            (ValidationError)   Validation error if found; else None
        """
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

            if self.node_status == NodeStatus.MANDATORY_DEPRECATED:
                violations.append(
                    ValidationError(
                        target=ValidationTargetType.NODE,
                        object_id=str(self._id),
                        validation_code=ValidationCode.DEPRECATED_NODE
                    ))

        if len(violations) == 0:
            return None

        return ValidationError(
            target=ValidationTargetType.NODE,
            object_id=str(self._id),
            validation_code=ValidationCode.IN_DEPENDENTS,
            children=violations
        )

    def apply_properties(self, other_node):
        """Apply Properties and Inputs of another Node.

        Args:
            other_node  (Node):     A node to copy Properties and Inputs from
        """
        for other_input in other_node.inputs:
            for input in self.inputs:
                if other_input.name == input.name:
                    if (input.max_count < 0 or input.max_count >= other_input.max_count) and set(input.file_types) >= set(other_input.file_types):
                        input.values = other_input.values
                    break

        for other_parameter in other_node.parameters:
            for parameter in self.parameters:
                if other_parameter.name == parameter.name:
                    if parameter.parameter_type == other_parameter.parameter_type and parameter.widget:
                        parameter.value = other_parameter.value
                    break

        self.description = other_node.description

        self.x = other_node.x
        self.y = other_node.y

    def __str__(self):
        return 'Node(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'Node({})'.format(str(self.to_dict()))

    def _get_custom_element(self, arr, name, throw):
        for parameter in arr:
            if parameter.name == name:
                return parameter
        if throw:
            raise Exception('Parameter "{}" not found in {}'.format(name, self.title))
        return None

    def get_input_by_name(self, name, throw=True):
        return self._get_custom_element(self.inputs, name, throw)

    def get_parameter_by_name(self, name, throw=True):
        return self._get_custom_element(self.parameters, name, throw)

    def get_output_by_name(self, name, throw=True):
        return self._get_custom_element(self.outputs, name, throw)

    def get_log_by_name(self, name, throw=True):
        return self._get_custom_element(self.logs, name, throw)
