"""Node DB Object and utils"""

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from dataclasses_json import dataclass_json
from past.builtins import basestring

from plynx.constants import Collections, NodeClonePolicy, NodeOrigin, NodeRunningStatus, NodeStatus, ParameterTypes, SpecialNodeId
from plynx.db.db_object import DBObject
from plynx.plugins.resources.common import FILE_KIND
from plynx.utils.common import ObjectId


# pylint: disable=too-many-branches
def _clone_update_in_place(node: "Node", node_clone_policy: int):
    if node.node_running_status == NodeRunningStatus.SPECIAL:
        for output in node.outputs:
            output.values = []
        return node
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
        raise Exception(f"Unknown clone policy `{node_clone_policy}`")

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
            for input in sub_node.inputs:   # pylint: disable=redefined-builtin
                input.values = []
                for input_reference in input.input_references:
                    input_reference.node_id = object_id_mapping[ObjectId(input_reference.node_id)]

            for parameter in sub_node.parameters:
                if not parameter.reference:
                    continue
                parameter.value = node.get_parameter_by_name(parameter.reference, throw=True).value

            if sub_node.node_running_status == NodeRunningStatus.STATIC:
                # do not copy the rest of the elements because they don't change
                continue

            for output in sub_node.outputs:
                output.values = []

            for log in sub_node.logs:
                log.values = []

    for output_or_log in node.outputs + node.logs:
        output_or_log.values = []
    return node


@dataclass_json
@dataclass
class _BaseResource(DBObject):
    name: str = ""
    file_type: str = FILE_KIND
    values: List[Any] = field(default_factory=list)
    is_array: bool = False
    min_count: int = 1


@dataclass_json
@dataclass
class Output(_BaseResource):
    """Basic Output structure."""


@dataclass_json
@dataclass
class InputReference(DBObject):
    """Basic Value of the Input structure."""

    node_id: str = ""
    output_id: str = ""


@dataclass_json
@dataclass
class Input(_BaseResource):
    """Basic Input structure."""

    input_references: List[InputReference] = field(default_factory=list)


@dataclass_json
@dataclass
class Node(DBObject):
    """Basic Node with db interface."""
    # pylint: disable=too-many-instance-attributes
    DB_COLLECTION = Collections.TEMPLATES

    _id: ObjectId = field(default_factory=ObjectId)
    _type: str = "Node"
    title: str = "Title"
    description: str = "Description"
    kind: str = "dummy"
    # ID of previous version of the node, always refer to `nodes` collection.
    parent_node_id: Optional[ObjectId] = None
    # ID of next version of the node, always refer to `nodes` collection.
    successor_node_id: Optional[ObjectId] = None
    # ID of original node, used in `runs`, always refer to `nodes` collection.
    # A Run refers to original node
    original_node_id: Optional[ObjectId] = None
    origin: str = NodeOrigin.DB
    # The following `code_*` values defined when the operation declared outside of plynx DB
    # code_hash is a hash value of the code
    code_hash: str = ""
    # code_function_location refers to the location of the function
    code_function_location: Optional[str] = None
    node_running_status: str = NodeRunningStatus.CREATED
    node_status: str = NodeStatus.CREATED
    cache_url: Optional[str] = None
    x: int = 0
    y: int = 0
    author: Optional[ObjectId] = None
    starred: bool = False

    inputs: List[Input] = field(default_factory=list)
    parameters: List["Parameter"] = field(default_factory=list)
    outputs: List[Output] = field(default_factory=list)
    logs: List[Output] = field(default_factory=list)

    @staticmethod
    def _default_log(name: str) -> Output:
        return Output(
            name=name,
            file_type=FILE_KIND,
            values=[],
            is_array=False,
            min_count=1,
        )

    # pylint: disable=attribute-defined-outside-init
    def apply_properties(self, other_node: "Node"):
        """Apply Properties and Inputs of another Node.
        This method is used for updating nodes.

        Args:
            other_node  (Node):     A node to copy Properties and Inputs from
        """
        for other_input in other_node.inputs:
            for input in self.inputs:   # pylint: disable=redefined-builtin
                if other_input.name == input.name and \
                   other_input.file_type == input.file_type and (
                            input.is_array or
                            (not input.is_array and 1 == len(other_input.input_references))
                       ):
                    input.input_references = other_input.input_references
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

    def clone(self, node_clone_policy: int) -> "Node":
        """Return a cloned copy of a Node"""
        node = _clone_update_in_place(Node.from_dict(self.to_dict()), node_clone_policy)
        return node

    def _get_custom_element(
                self,
                arr: Union[List[Input], List["Parameter"], List[Output]],
                name: str,
                throw: bool,
                default: Optional[Callable[[str], Union[Input, "Parameter", Output]]] = None
            ):
        for obj in arr:
            if obj.name == name:
                return obj
        if throw:
            raise Exception(f'Object "{name}" not found in {self.title}')
        if default:
            arr.append(default(name=name))  # type: ignore
            return arr[-1]
        return None

    def get_input_by_name(self, name: str, throw: bool = True):
        """Find Input object"""
        return self._get_custom_element(self.inputs, name, throw)

    def get_parameter_by_name(self, name: str, throw: bool = True):
        """Find Parameter object"""
        return self._get_custom_element(self.parameters, name, throw)

    def get_output_by_name(self, name: str, throw: bool = True):
        """Find Output object"""
        return self._get_custom_element(self.outputs, name, throw)

    def get_log_by_name(self, name: str, throw: bool = False):
        """Find Log object"""
        return self._get_custom_element(self.logs, name, throw, default=Node._default_log)

    # pylint: disable=inconsistent-return-statements
    def arrange_auto_layout(self, readonly: bool = False):
        """Use heuristic to rearange nodes."""
        # pylint: disable=invalid-name,too-many-locals,too-many-statements
        HEADER_HEIGHT = 23
        TITLE_HEIGHT = 20
        FOOTER_HEIGHT = 10
        BORDERS_HEIGHT = 2
        ITEM_HEIGHT = 20
        SPACE_HEIGHT = 50
        LEFT_PADDING = 30
        TOP_PADDING = 80
        LEVEL_WIDTH = 252
        SPECIAL_PARAMETER_HEIGHT = 20
        SPECIAL_PARAMETER_TYPES = [ParameterTypes.CODE]
        min_node_height = HEADER_HEIGHT + TITLE_HEIGHT + FOOTER_HEIGHT + BORDERS_HEIGHT

        node_id_to_level = defaultdict(lambda: -1)
        node_id_to_node = {}
        queued_node_ids = set()
        children_ids = defaultdict(set)

        sub_nodes = self.get_parameter_by_name('_nodes').value.value

        if len(sub_nodes) == 0:
            return

        node_ids = {node._id for node in sub_nodes}
        non_zero_node_ids = set()
        for node in sub_nodes:
            node_id_to_node[node._id] = node
            for input in node.inputs:   # pylint: disable=redefined-builtin
                for input_reference in input.input_references:
                    parent_node_id = ObjectId(input_reference.node_id)
                    non_zero_node_ids.add(parent_node_id)
                    children_ids[parent_node_id].add(node._id)

        leaves = node_ids - non_zero_node_ids
        to_visit: deque = deque()
        # Alwasy put Output Node in the end
        push_special = SpecialNodeId.OUTPUT in leaves and len(leaves) > 1
        for leaf_id in leaves:
            node_id_to_level[leaf_id] = 1 if push_special and leaf_id != SpecialNodeId.OUTPUT else 0
            to_visit.append(leaf_id)

        while to_visit:
            node_id = to_visit.popleft()
            node = node_id_to_node[node_id]
            node_level = max([node_id_to_level[node_id]] + [node_id_to_level[child_id] + 1 for child_id in children_ids[node_id]])
            node_id_to_level[node_id] = node_level
            for input in node.inputs:   # pylint: disable=redefined-builtin
                for input_reference in input.input_references:
                    parent_node_id = ObjectId(input_reference.node_id)
                    parent_level = node_id_to_level[parent_node_id]
                    node_id_to_level[parent_node_id] = max(node_level + 1, parent_level)
                    if parent_node_id not in queued_node_ids:
                        to_visit.append(parent_node_id)
                        queued_node_ids.add(parent_node_id)

        max_level = max(node_id_to_level.values())
        level_to_node_ids: Dict[int, List[ObjectId]] = defaultdict(list)
        row_heights: Dict[int, int] = defaultdict(lambda: 0)

        def get_index_helper(node, level):
            if level < 0:
                return 0
            parent_node_ids = set()
            for input in node.inputs:   # pylint: disable=redefined-builtin
                for input_reference in input.input_references:
                    parent_node_ids.add(ObjectId(input_reference.node_id))

            for index, node_id in enumerate(level_to_node_ids[level]):
                if node_id in parent_node_ids:
                    return index
            return -1

        def get_index(node, max_level, level):
            # pylint: disable=consider-using-generator
            return tuple(
                [get_index_helper(node, lvl) for lvl in range(max_level, level, -1)]
            )

        for node_id, level in node_id_to_level.items():
            level_to_node_ids[level].append(node_id)

        # Push Input Node up the level
        if SpecialNodeId.INPUT in node_id_to_level and \
                (node_id_to_level[SpecialNodeId.INPUT] != max_level or len(level_to_node_ids[max_level]) > 1):
            input_level = node_id_to_level[SpecialNodeId.INPUT]
            level_to_node_ids[input_level] = [node_id for node_id in level_to_node_ids[input_level] if node_id != SpecialNodeId.INPUT]
            max_level += 1
            node_id_to_level[SpecialNodeId.INPUT] = max_level
            level_to_node_ids[max_level] = [SpecialNodeId.INPUT]

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
        for index, _ in enumerate(row_heights):
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


@dataclass_json
@dataclass
class ParameterEnum(DBObject):
    """Enum value."""
    values: List[str] = field(default_factory=list)
    index: int = 0


@dataclass_json
@dataclass
class ParameterCode(DBObject):
    """Code value."""
    value: str = ""
    mode: str = "python"


@dataclass_json
@dataclass
class ParameterListOfNodes(DBObject):
    """List Of Nodes value."""
    value: List[Node] = field(default_factory=list)


# pylint: disable=too-many-return-statements
def _get_default_by_type(parameter_type: str):
    if parameter_type == ParameterTypes.STR:
        return ''
    if parameter_type == ParameterTypes.INT:
        return 0
    if parameter_type == ParameterTypes.FLOAT:
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


def _value_is_valid(value, parameter_type: str):
    if parameter_type == ParameterTypes.STR:
        return isinstance(value, basestring)
    if parameter_type == ParameterTypes.INT:
        try:
            int(value)
        except ValueError:
            return False
        return True
    if parameter_type == ParameterTypes.FLOAT:
        try:
            float(str(value))
        except ValueError:
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


@dataclass_json
@dataclass
class Parameter(DBObject):
    """Basic Parameter structure."""
    # pylint: disable=too-many-instance-attributes

    name: str = ""
    parameter_type: str = ParameterTypes.STR
    # TODO make type factory
    value: Any = ""
    mutable_type: bool = True
    removable: bool = True
    publicable: bool = True
    widget: Optional[str] = None
    reference: Optional[str] = None

    def __post_init__(self):
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
            raise ValueError(f"Invalid parameter value type: {self.name}: {self.value}")
