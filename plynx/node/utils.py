"""General PLynx utils for user-defined Operations."""
import hashlib
from dataclasses import dataclass
from typing import Callable, Union

from plynx.constants import NodeOrigin, NodeRunningStatus, NodeStatus
from plynx.db.node import Node
from plynx.utils.common import ObjectId


@dataclass
class Group:
    """Collection of Operations"""
    title: str
    items: list

    def to_dict(self):
        """Dict representation"""
        return {
            "_id": str(ObjectId()),
            "_type": "Group",
            "title": self.title,
            "items": list(map(func_or_group_to_dict, self.items)),  # pylint: disable=redefined-builtin
        }


def callable_to_function_location(callable_obj: Callable) -> str:
    """Generate the location of the function"""
    return ".".join([callable_obj.__module__, callable_obj.__name__])


def generate_key(node: Node) -> str:
    """
    Generate hash of the node template.
    """

    sorted_inputs = sorted(node.inputs, key=lambda x: x.name)
    inputs_hash = ','.join([
        f"{input.name}:{input.file_type}:{input.is_array}:{input.min_count}"
        for input in sorted_inputs
    ])

    sorted_parameters = sorted(node.parameters, key=lambda x: x.name)
    parameters_hash = ','.join([
        f"{parameter.name}:{parameter.parameter_type}"
        for parameter in sorted_parameters
    ])

    sorted_outputs = sorted(node.outputs, key=lambda x: x.name)
    outputs_hash = ','.join([
        f"{output.name}:{output.file_type}:{output.is_array}:{output.min_count}"
        for output in sorted_outputs
    ])

    assert node.code_function_location, "`code_function_location` must not be empty"
    hash_str = ';'.join([
        node.code_function_location,
        inputs_hash,
        parameters_hash,
        outputs_hash,
    ])

    return hashlib.sha256(hash_str.encode('utf-8')).hexdigest()


def func_or_group_to_dict(func_or_group: Union[Callable, Group]):
    """Recursive serializer"""
    if isinstance(func_or_group, Group):
        return func_or_group.to_dict()
    plynx_params = func_or_group.plynx_params   # type: ignore

    raw_node = {
        "_id": str(ObjectId()),
        "_type": "Node",
        "title": plynx_params.title,
        "description": plynx_params.description,
        "node_running_status": NodeRunningStatus.CREATED,
        "node_status": NodeStatus.READY,
        "author": None,
        "auto_run_enabled": plynx_params.auto_run_enabled,
        "kind": plynx_params.kind,
        "origin": NodeOrigin.BUILT_IN_HUBS,
        "code_function_location": callable_to_function_location(func_or_group),
        "inputs": list(map(lambda item: item.to_dict(), plynx_params.inputs)),
        "outputs": list(map(lambda item: item.to_dict(), plynx_params.outputs)),
        "parameters": list(map(lambda item: item.to_dict(), plynx_params.params)),
        "logs": [],
    }
    node = Node.from_dict(raw_node)
    node.code_hash = generate_key(node)

    return node.to_dict()
