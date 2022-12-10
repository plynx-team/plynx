"""Node DB Object and utils"""
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Union

from dataclasses_json import dataclass_json
from past.builtins import basestring

from plynx.constants import Collections, NodeClonePolicy, NodeOrigin, NodeRunningStatus, NodeStatus, ParameterTypes
from plynx.db.db_object import DBObject
from plynx.plugins.resources.common import FILE_KIND
from plynx.utils.common import ObjectId


# pylint: disable=too-many-branches
def _clone_update_in_place(node: "Node", node_clone_policy: int, override_finished_state: bool, override_node_id: bool = False):
    if node.node_running_status == NodeRunningStatus.SPECIAL:
        for output in node.outputs:
            output.values = []
        return node
    old_node_id = node._id
    node.template_node_id = node._id
    if override_node_id:
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

    if override_finished_state or not NodeRunningStatus.is_succeeded(node.node_running_status):
        node.node_running_status = NodeRunningStatus.READY
    node.node_status = NodeStatus.CREATED

    sub_nodes = node.get_parameter_by_name('_nodes', throw=False)
    if sub_nodes:
        object_id_mapping = {}
        for sub_node in sub_nodes.value.value:
            prev_id = ObjectId(sub_node._id)
            _clone_update_in_place(sub_node, node_clone_policy, override_finished_state)
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

            if override_finished_state or not NodeRunningStatus.is_succeeded(sub_node.node_running_status):
                for output in sub_node.outputs:
                    output.values = []

                for log in sub_node.logs:
                    log.values = []

    if override_finished_state or not NodeRunningStatus.is_succeeded(node.node_running_status):
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

    thumbnail: Optional[str] = None


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
class CachedNode(DBObject):
    """Values to override Node on display"""
    node_running_status: str = NodeRunningStatus.CREATED
    outputs: List[Output] = field(default_factory=list)
    logs: List[Output] = field(default_factory=list)


@dataclass_json
@dataclass
class Node(DBObject):
    """Basic Node with db interface."""
    # pylint: disable=too-many-instance-attributes
    DB_COLLECTION = Collections.TEMPLATES

    _id: ObjectId = field(default_factory=ObjectId)
    _type: str = "Node"
    _cached_node: Optional[CachedNode] = None
    title: str = "Title"
    description: str = ""
    kind: str = "dummy"
    # ID of previous version of the node, always refer to `nodes` collection.
    parent_node_id: Optional[ObjectId] = None
    # ID of next version of the node, always refer to `nodes` collection.
    successor_node_id: Optional[ObjectId] = None
    # ID of original node, used in `runs`, always refer to `nodes` collection.
    # A Run refers to original node
    original_node_id: Optional[ObjectId] = None
    template_node_id: Optional[ObjectId] = None
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
    auto_sync: bool = True
    auto_run: bool = True
    auto_run_enabled: bool = True
    # latest_run_id would be used in Templates to refer to the current run
    latest_run_id: Optional[ObjectId] = None

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

    def clone(self, node_clone_policy: int, override_finished_state: bool = True) -> "Node":
        """Return a cloned copy of a Node"""
        node = _clone_update_in_place(Node.from_dict(self.to_dict()), node_clone_policy, override_finished_state, override_node_id=True)
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

    def get_sub_nodes(self):
        """Get a list of subnodes"""
        sub_nodes_parameter = self.get_parameter_by_name('_nodes', throw=False)
        if not sub_nodes_parameter:
            raise Exception("Subnodes not found")
        return sub_nodes_parameter.value.value


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
