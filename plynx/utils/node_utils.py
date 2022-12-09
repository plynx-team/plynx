"""This module contais utils related to plynx.db.Node, but not necessary involved into DB structure"""
import hashlib
from collections import deque
from typing import Deque

from plynx.constants import IGNORED_CACHE_PARAMETERS
from plynx.db.node import CachedNode, Node
from plynx.utils.common import ObjectId, to_object_id


class _GraphVertex:
    """Used for internal purposes."""

    def __init__(self):
        self.edges = []
        self.num_connections = 0


class GraphError(Exception):
    """Generic Graph topology exception"""


def _generate_parameters_key(node: Node) -> str:
    """Generate hash key based on parameters only.

    Args:
        node    (Node): Node object

    Return:
        (str)   Hash value
    """

    parameters = node.parameters

    sorted_parameters = sorted(parameters, key=lambda x: x.name)
    parameters_hash = ','.join([
        f"{parameter.name}:{parameter.value}"
        for parameter in sorted_parameters if parameter.name not in IGNORED_CACHE_PARAMETERS
    ])

    return hashlib.sha256(
        ';'.join([
                parameters_hash,
            ]).encode('utf-8')
    ).hexdigest()


# pylint: disable=too-many-locals
def augment_node_with_cache(self, other_node: Node) -> None:
    """
    Augment the Node in templates with a Node in Run.
    Results will be stored in `_cached_node` fields of the subnodes and not applied directly.
    """
    # pylint: disable=too-many-branches
    # TODO optimize function and remove too-many-locals
    self._cached_node = None
    sub_nodes_parameter = self.get_parameter_by_name('_nodes', throw=False)
    if not sub_nodes_parameter:
        # TODO check if cacheable
        # TODO probably never called.
        # TODO Update when run augmentation recursevely
        raise NotImplementedError("Subnodes are not found")

    sub_nodes = sub_nodes_parameter.value.value
    other_sub_nodes = other_node.get_parameter_by_name('_nodes').value.value
    other_node_id_to_original_id = {}
    for other_sub_node in other_sub_nodes:
        other_node_id_to_original_id[other_sub_node._id] = other_sub_node.template_node_id

    id_to_node = {}
    for sub_node in sub_nodes:
        sub_node._cached_node = None
        obj_id = to_object_id(sub_node._id)
        id_to_node[obj_id] = sub_node

    for other_subnode in traverse_in_order(other_node):
        if other_subnode.template_node_id not in id_to_node:
            continue
        sub_node = id_to_node[other_subnode.template_node_id]

        # TODO: check is final state
        this_cache = _generate_parameters_key(sub_node)
        other_node_cache = _generate_parameters_key(other_subnode)

        if this_cache != other_node_cache:
            continue

        tmp_inputs = []
        for input in sub_node.inputs:   # pylint: disable=redefined-builtin
            for input_reference in input.input_references:
                tmp_inputs.append(f"{input_reference.node_id}-{input_reference.output_id}")
        sub_node_inputs_hash = ",".join(tmp_inputs)

        tmp_inputs = []
        for input in other_subnode.inputs:  # pylint: disable=redefined-builtin
            for input_reference in input.input_references:
                orig_idx = other_node_id_to_original_id.get(to_object_id(input_reference.node_id), 'none')
                tmp_inputs.append(f"{orig_idx}-{input_reference.output_id}")
        other_subnode_inputs_hash = ",".join(tmp_inputs)

        if sub_node_inputs_hash != other_subnode_inputs_hash:
            continue

        tmp_refs_is_cached = False
        for input in sub_node.inputs:
            for input_reference in input.input_references:
                ref_node_id = input_reference.node_id
                if id_to_node[to_object_id(ref_node_id)]._cached_node is None:
                    tmp_refs_is_cached = True
        if tmp_refs_is_cached:
            continue

        sub_node._cached_node = CachedNode(
            node_running_status=other_subnode.node_running_status,
            outputs=other_subnode.outputs,
            logs=other_subnode.logs,
        )


def traverse_reversed(node: Node):
    """
    Traverse the subnodes in a reversed from the topoligical order.
    """
    # pylint: disable=too-many-branches
    sub_nodes_parameter = node.get_parameter_by_name('_nodes', throw=False)
    if not sub_nodes_parameter:
        yield node
        return

    sub_nodes = sub_nodes_parameter.value.value
    if len(sub_nodes) == 0:
        return

    id_to_vertex = {sub_node._id: _GraphVertex() for sub_node in sub_nodes}
    dfs_queue: Deque[ObjectId] = deque()
    node_index = {}

    for sub_node in sub_nodes:
        node_index[sub_node._id] = sub_node
        for input in sub_node.inputs:   # pylint: disable=redefined-builtin
            for input_reference in input.input_references:
                ref_node_id = to_object_id(input_reference.node_id)
                id_to_vertex[sub_node._id].edges.append(ref_node_id)
                id_to_vertex[ref_node_id].num_connections += 1

    for vertex_id, vertex in id_to_vertex.items():
        if vertex.num_connections == 0:
            dfs_queue.append(vertex_id)

    if len(dfs_queue) == 0:
        raise GraphError("No node without outgoing output found")

    while dfs_queue:
        node_id = dfs_queue.popleft()
        yield node_index[node_id]
        for vertex_id in id_to_vertex[node_id].edges:
            id_to_vertex[vertex_id].num_connections -= 1
            if id_to_vertex[vertex_id].num_connections == 0:
                dfs_queue.append(vertex_id)

    for vertex_id, vertex in id_to_vertex.items():
        if vertex.num_connections != 0:
            raise GraphError("Unresolved connections")


def traverse_in_order(node: Node):
    """
    Traverse the subnodes in a topoligical order.
    """
    nodes = list(traverse_reversed(node))
    return reversed(nodes)
