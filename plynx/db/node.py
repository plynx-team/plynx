from past.builtins import basestring
from collections import defaultdict, deque
from plynx.constants import Collections, NodeClonePolicy
from plynx.db.db_object import DBObject, DBObjectField
from plynx.db.validation_error import ValidationError
from plynx.utils.common import ObjectId
from plynx.constants import NodeStatus, NodeRunningStatus, ValidationTargetType, ValidationCode
from plynx.plugins.resources.common import File as FileCls
from plynx.constants import ParameterTypes


def _clone_update_in_place(node, node_clone_policy):
    old_node_id = node._id
    node._id = ObjectId()
    node.successor_node_id = None
    if node_clone_policy == NodeClonePolicy.NODE_TO_NODE:
        node.parent_node_id = old_node_id
        node.original_node_id = None
    elif node_clone_policy == NodeClonePolicy.NODE_TO_RUN:
        node.parent_node_id = None
        node.original_node_id = node.original_node_id or old_node_id
    elif node_clone_policy == NodeClonePolicy.RUN_TO_NODE:
        node.parent_node_id = node.original_node_id
        node.original_node_id = None
    else:
        raise Exception('Unknown clone policy `{}`'.format(node_clone_policy))

    if node.node_running_status == NodeRunningStatus.STATIC:
        return node
    node.node_running_status = NodeRunningStatus.READY
    node.node_status = NodeStatus.CREATED

    sub_nodes = node.get_parameter_by_name('_nodes', throw=False)
    if sub_nodes:
        object_id_mapping = {}
        for sub_node in sub_nodes.value.value:
            prev_id = ObjectId(sub_node._id)
            _clone_update_in_place(sub_node, node_clone_policy)
            object_id_mapping[prev_id] = sub_node._id

        for sub_node in sub_nodes.value.value:
            for input in sub_node.inputs:
                for input_value in input.values:
                    input_value.node_id = object_id_mapping[ObjectId(input_value.node_id)]

    for output_or_log in node.outputs + node.logs:
        output_or_log.resource_id = None
    return node


class Output(DBObject):
    """Basic Output structure."""

    FIELDS = {
        'name': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'file_type': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'resource_id': DBObjectField(
            type=str,
            default=None,
            is_list=False,
            ),
    }

    def __str__(self):
        return 'Output(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Output({})'.format(str(self.to_dict()))


class InputValue(DBObject):
    """Basic Value of the Input structure."""

    FIELDS = {
        'node_id': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'output_id': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'resource_id': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
    }

    def __str__(self):
        return 'InputValue({}, {})'.format(self.node_id, self.output_id)

    def __repr__(self):
        return 'InputValue({})'.format(str(self.to_dict()))


class Input(DBObject):
    """Basic Input structure."""

    FIELDS = {
        'name': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'file_types': DBObjectField(
            type=str,
            default=list,
            is_list=True,
            ),
        'values': DBObjectField(
            type=InputValue,
            default=list,
            is_list=True,
            ),
        'min_count': DBObjectField(
            type=int,
            default=1,
            is_list=False,
            ),
        'max_count': DBObjectField(
            type=int,
            default=1,
            is_list=False,
            ),
        }

    def __str__(self):
        return 'Input(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Input({})'.format(str(self.to_dict()))


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
        # Kind, such as plynx.plugins.executors.local.BashJinja2. Derived from from plynx.plugins.executors.BaseExecutor class.
        'kind': DBObjectField(
            type=str,
            default='bash_jinja2',
            is_list=False,
            ),
        # ID of previous version of the node, always refer to `nodes` collection.
        'parent_node_id': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        # ID of next version of the node, always refer to `nodes` collection.
        'successor_node_id': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        # ID of original node, used in `runs`, always refer to `nodes` collection.
        # A Run refers to original node
        'original_node_id': DBObjectField(
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
            type=lambda object_dict: Parameter(object_dict),
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

    DB_COLLECTION = Collections.TEMPLATES

    def _DEFAULT_LOG(name):
        return Output.from_dict({
            'name': name,
            'file_type': FileCls.NAME,
            'resource_id': None,
        })

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

    def clone(self, node_clone_policy):
        return _clone_update_in_place(self.copy(), node_clone_policy)

    def __str__(self):
        return 'Node(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'Node({})'.format(str(self.to_dict()))

    def _get_custom_element(self, arr, name, throw, default=None):
        for parameter in arr:
            if parameter.name == name:
                return parameter
        if throw:
            raise Exception('Parameter "{}" not found in {}'.format(name, self.title))
        if default:
            arr.append(default(name))
            return arr[-1]
        return None

    def get_input_by_name(self, name, throw=True):
        return self._get_custom_element(self.inputs, name, throw)

    def get_parameter_by_name(self, name, throw=True):
        return self._get_custom_element(self.parameters, name, throw)

    def get_output_by_name(self, name, throw=True):
        return self._get_custom_element(self.outputs, name, throw)

    def get_log_by_name(self, name, throw=False):
        return self._get_custom_element(self.logs, name, throw, default=Node._DEFAULT_LOG)

    def arrange_auto_layout(self, readonly=False):
        """Use heuristic to rearange nodes."""
        HEADER_HEIGHT = 23
        DESCRIPTION_HEIGHT = 20
        FOOTER_HEIGHT = 10
        BORDERS_HEIGHT = 2
        ITEM_HEIGHT = 20
        SPACE_HEIGHT = 50
        LEFT_PADDING = 30
        TOP_PADDING = 80
        LEVEL_WIDTH = 252
        SPECIAL_PARAMETER_HEIGHT = 20
        SPECIAL_PARAMETER_TYPES = [ParameterTypes.CODE]
        min_node_height = HEADER_HEIGHT + DESCRIPTION_HEIGHT + FOOTER_HEIGHT + BORDERS_HEIGHT

        node_id_to_level = defaultdict(lambda: -1)
        node_id_to_node = {}
        queued_node_ids = set()
        children_ids = defaultdict(set)

        sub_nodes = self.get_parameter_by_name('_nodes')

        node_ids = set([node._id for node in sub_nodes.value.value])
        non_zero_node_ids = set()
        for node in sub_nodes.value.value:
            node_id_to_node[node._id] = node
            for input in node.inputs:
                for value in input.values:
                    parent_node_id = ObjectId(value.node_id)
                    non_zero_node_ids.add(parent_node_id)
                    children_ids[parent_node_id].add(node._id)

        leaves = node_ids - non_zero_node_ids
        to_visit = deque()
        for leaf_id in leaves:
            node_id_to_level[leaf_id] = 0
            to_visit.append(leaf_id)

        while to_visit:
            node_id = to_visit.popleft()
            node = node_id_to_node[node_id]
            node_level = max([node_id_to_level[node_id]] + [node_id_to_level[child_id] + 1 for child_id in children_ids[node_id]])
            node_id_to_level[node_id] = node_level
            for input in node.inputs:
                for value in input.values:
                    parent_node_id = ObjectId(value.node_id)
                    parent_level = node_id_to_level[parent_node_id]
                    node_id_to_level[parent_node_id] = max(node_level + 1, parent_level)
                    if parent_node_id not in queued_node_ids:
                        to_visit.append(parent_node_id)
                        queued_node_ids.add(parent_node_id)

        max_level = max(node_id_to_level.values())
        level_to_node_ids = defaultdict(list)
        row_heights = defaultdict(lambda: 0)

        def get_index_helper(node, level):
            if level < 0:
                return 0
            parent_node_ids = set()
            for input in node.inputs:
                for value in input.values:
                    parent_node_ids.add(ObjectId(value.node_id))

            for index, node_id in enumerate(level_to_node_ids[level]):
                if node_id in parent_node_ids:
                    return index
            return -1

        def get_index(node, max_level, level):
            return tuple(
                [get_index_helper(node, lvl) for lvl in range(max_level, level, -1)]
            )

        for node_id, level in node_id_to_level.items():
            level_to_node_ids[level].append(node_id)

        # level_to_node_ids, node_id_to_node,

        for level in range(max_level, -1, -1):
            level_node_ids = level_to_node_ids[level]
            index_to_node_id = []
            for node_id in level_node_ids:
                node = node_id_to_node[node_id]
                index = get_index(node, max_level, level)
                index_to_node_id.append((index, node_id))

            index_to_node_id.sort()
            level_to_node_ids[level] = [node_id for _, node_id in index_to_node_id]

            for index, node_id in enumerate(level_to_node_ids[level]):
                node = node_id_to_node[node_id]
                special_parameters_count = sum(
                    1 if parameter.parameter_type in SPECIAL_PARAMETER_TYPES and parameter.widget else 0
                    for parameter in node.parameters
                )
                node_height = sum([
                    min_node_height,
                    ITEM_HEIGHT * max(len(node.inputs), len(node.outputs)),
                    special_parameters_count * SPECIAL_PARAMETER_HEIGHT
                ])
                row_heights[index] = max(row_heights[index], node_height)

        # TODO compute grid in a separate function
        if readonly:
            return level_to_node_ids, node_id_to_node

        cum_heights = [0]
        for index in range(len(row_heights)):
            cum_heights.append(cum_heights[-1] + row_heights[index] + SPACE_HEIGHT)

        max_height = max(cum_heights)

        for level in range(max_level, -1, -1):
            level_node_ids = level_to_node_ids[level]
            level_height = cum_heights[len(level_node_ids)]
            level_padding = (max_height - level_height) // 2
            for index, node_id in enumerate(level_node_ids):
                node = node_id_to_node[node_id]
                node.x = LEFT_PADDING + (max_level - level) * LEVEL_WIDTH
                node.y = TOP_PADDING + level_padding + cum_heights[index]

        return None, None


class ParameterEnum(DBObject):
    """Enum value."""

    FIELDS = {
        'values': DBObjectField(
            type=str,
            default=list,
            is_list=True,
            ),
        'index': DBObjectField(
            type=str,
            default=-1,
            is_list=False,
            ),
    }

    def __repr__(self):
        return 'ParameterEnum({})'.format(str(self.to_dict()))


class ParameterCode(DBObject):
    """Code value."""

    FIELDS = {
        'value': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'mode': DBObjectField(
            type=str,
            default='python',
            is_list=False,
            ),
    }

    def __repr__(self):
        return 'ParameterCode({})'.format(str(self.to_dict()))


class ParameterListOfNodes(DBObject):
    """List Of Nodes value."""

    FIELDS = {
        'value': DBObjectField(
            type=Node,
            default=list,
            is_list=True,
            ),
    }

    def __repr__(self):
        return 'ParameterListOfNodes({})'.format(str(self.to_dict()))


def _get_default_by_type(parameter_type):
    if parameter_type == ParameterTypes.STR:
        return ''
    if parameter_type == ParameterTypes.INT:
        return 0
    if parameter_type == ParameterTypes.BOOL:
        return False
    if parameter_type == ParameterTypes.TEXT:
        return ''
    if parameter_type == ParameterTypes.ENUM:
        return ParameterEnum()
    if parameter_type == ParameterTypes.LIST_STR:
        return []
    if parameter_type == ParameterTypes.LIST_INT:
        return []
    elif parameter_type == ParameterTypes.LIST_NODE:
        return ParameterListOfNodes()
    elif parameter_type == ParameterTypes.CODE:
        return ParameterCode()
    else:
        return None


def _value_is_valid(value, parameter_type):
    if parameter_type == ParameterTypes.STR:
        return isinstance(value, basestring)
    if parameter_type == ParameterTypes.INT:
        try:
            int(value)
        except Exception:
            return False
        return True
    if parameter_type == ParameterTypes.BOOL:
        return isinstance(value, int)
    if parameter_type == ParameterTypes.TEXT:
        return isinstance(value, basestring)
    if parameter_type == ParameterTypes.ENUM:
        return isinstance(value, ParameterEnum)
    if parameter_type == ParameterTypes.LIST_STR:
        return isinstance(value, list) and all(_value_is_valid(x, ParameterTypes.STR) for x in value)
    if parameter_type == ParameterTypes.LIST_INT:
        return isinstance(value, list) and all(_value_is_valid(x, ParameterTypes.INT) for x in value)
    elif parameter_type == ParameterTypes.LIST_NODE:
        # TODO proper validation
        return isinstance(value, ParameterListOfNodes)
    if parameter_type == ParameterTypes.CODE:
        return isinstance(value, ParameterCode)
    else:
        return False


# TODO remove Widget
class ParameterWidget(DBObject):
    """Basic ParameterWidget structure."""

    FIELDS = {
        'alias': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
    }

    def __str__(self):
        return 'ParameterWidget(alias="{}")'.format(self.alias)

    def __repr__(self):
        return 'ParameterWidget({})'.format(str(self.to_dict()))


class Parameter(DBObject):
    """Basic Parameter structure."""

    FIELDS = {
        'name': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'parameter_type': DBObjectField(
            type=str,
            default=ParameterTypes.STR,
            is_list=False,
            ),
        # TODO make type factory
        'value': DBObjectField(
            type=lambda x: x,   # Preserve type
            default='',
            is_list=False,
            ),
        'mutable_type': DBObjectField(
            type=bool,
            default=True,
            is_list=False,
            ),
        'removable': DBObjectField(
            type=bool,
            default=True,
            is_list=False,
            ),
        'publicable': DBObjectField(
            type=bool,
            default=True,
            is_list=False,
            ),
        'widget': DBObjectField(
            type=str,
            default=None,
            is_list=False,
            ),
    }

    def __init__(self, obj_dict=None):
        super(Parameter, self).__init__(obj_dict)

        # `value` field is a special case: the type depends on `parameter_type`
        if self.value is None:
            self.value = _get_default_by_type(self.parameter_type)
        elif self.parameter_type == ParameterTypes.ENUM:
            self.value = ParameterEnum.from_dict(self.value)
        elif self.parameter_type == ParameterTypes.CODE:
            self.value = ParameterCode.from_dict(self.value)
        elif self.parameter_type == ParameterTypes.LIST_NODE:
            self.value = ParameterListOfNodes.from_dict(self.value)
        if not _value_is_valid(self.value, self.parameter_type):
            raise ValueError("Invalid parameter value type: {}: {}".format(self.name, self.value))

    def __str__(self):
        return 'Parameter(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Parameter({})'.format(str(self.to_dict()))
