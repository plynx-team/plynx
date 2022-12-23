"""This module contais utils related to plynx.db.Node, but not necessary involved into DB structure"""
import hashlib
import logging as logger
from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Set, Tuple

import plynx.db.node_collection_manager
from plynx.constants import IGNORED_CACHE_PARAMETERS, Collections, NodeClonePolicy, NodeRunningStatus, ParameterTypes, SpecialNodeId
from plynx.db.node import CachedNode, Node
from plynx.utils.common import ObjectId, to_object_id

node_collection_managers = {
    collection: plynx.db.node_collection_manager.NodeCollectionManager(collection=collection)
    for collection in [Collections.TEMPLATES, Collections.RUNS]
}


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
def augment_node_with_cache(node: Node, other_node: Node) -> None:
    """
    Augment the Node in templates with a Node in Run.
    Results will be stored in `_cached_node` fields of the subnodes and not applied directly.
    """
    # pylint: disable=too-many-branches
    # TODO optimize function and remove too-many-locals
    node._cached_node = None
    sub_nodes_parameter = node.get_parameter_by_name('_nodes', throw=False)
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


# pylint: disable=inconsistent-return-statements
def arrange_auto_layout(node: Node, readonly: bool = False):
    """Use heuristic to rearange nodes."""
    # pylint: disable=invalid-name,too-many-branches,too-many-locals,too-many-statements
    HEADER_HEIGHT = 23
    TITLE_HEIGHT = 20
    FOOTER_HEIGHT = 10
    BORDERS_HEIGHT = 2
    # ITEM_HEIGHT = 20
    ITEM_HEIGHT = 30
    OUTPUT_ITEM_HEIGHT = 100
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

    sub_nodes = node.get_parameter_by_name('_nodes').value.value

    if len(sub_nodes) == 0:
        return

    node_ids = {node._id for node in sub_nodes}
    non_zero_node_ids = set()
    for sub_node in sub_nodes:
        node_id_to_node[node._id] = sub_node
        for input in sub_node.inputs:   # pylint: disable=redefined-builtin
            for input_reference in input.input_references:
                parent_node_id = ObjectId(input_reference.node_id)
                non_zero_node_ids.add(parent_node_id)
                children_ids[parent_node_id].add(sub_node._id)

    leaves = node_ids - non_zero_node_ids
    to_visit: deque = deque()
    # Alwasy put Output Node in the end
    push_special = SpecialNodeId.OUTPUT in leaves and len(leaves) > 1
    for leaf_id in leaves:
        node_id_to_level[leaf_id] = 1 if push_special and leaf_id != SpecialNodeId.OUTPUT else 0
        to_visit.append(leaf_id)

    while to_visit:
        node_id = to_visit.popleft()
        sub_node = node_id_to_node[node_id]
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
                ITEM_HEIGHT * len(node.inputs) + OUTPUT_ITEM_HEIGHT * len(node.outputs),
                special_parameters_count * SPECIAL_PARAMETER_HEIGHT
            ])
            row_heights[index] = max(row_heights[index], node_height)

    # TODO compute grid in a separate function
    if readonly:
        return level_to_node_ids, node_id_to_node

    cum_heights = [0]
    for row_height in row_heights:
        cum_heights.append(cum_heights[-1] + row_height + SPACE_HEIGHT)

    max_height = max(cum_heights)

    for level in range(max_level, -1, -1):
        level_node_ids = level_to_node_ids[level]
        level_height = cum_heights[len(level_node_ids)]
        level_padding = (max_height - level_height) // 2
        for index, node_id in enumerate(level_node_ids):
            node = node_id_to_node[node_id]
            node.x = LEFT_PADDING + (max_level - level) * LEVEL_WIDTH
            node.y = TOP_PADDING + level_padding + cum_heights[index]


def apply_cache(node: Node):
    """Apply cache values to outputs and logs"""
    sub_nodes_parameter = node.get_parameter_by_name('_nodes', throw=False)
    if not sub_nodes_parameter:
        # TODO check if cacheable
        raise NotImplementedError("Subnodes not found. Do we want to be here?")

    sub_nodes = sub_nodes_parameter.value.value

    for sub_node in sub_nodes:
        if not sub_node._cached_node:
            continue
        sub_node.node_running_status = sub_node._cached_node.node_running_status
        sub_node.outputs = sub_node._cached_node.outputs
        sub_node.logs = sub_node._cached_node.logs

        sub_node._cached_node = None


def is_all_cached_and_successful(node: Node):
    """
    Check if the Node in a run needs recomputing at all.
    """
    sub_nodes_parameter = node.get_parameter_by_name('_nodes', throw=False)
    if not sub_nodes_parameter:
        # TODO check if cacheable
        return True

    sub_nodes = sub_nodes_parameter.value.value

    for sub_node in sub_nodes:
        if not sub_node._cached_node:
            return False
        if NodeRunningStatus.is_failed(sub_node._cached_node.node_running_status):
            return False
    return True


def construct_new_run(node: Node, user_id) -> Tuple[Optional[Node], Node]:
    """
    Create a new run based on a Node itself and the latest run as well.
    """
    node = Node.from_dict(node.to_dict())
    node_in_run: Optional[Node] = None
    if node.latest_run_id:
        node_in_run_dict = node_collection_managers[Collections.RUNS].get_db_node(node.latest_run_id, user_id)

        if node_in_run_dict:
            node_in_run = Node.from_dict(
                node_in_run_dict
            )
            augment_node_with_cache(node, node_in_run)
            apply_cache(node)
        else:
            logger.warning(f"Failed to load a run with id `{node.latest_run_id}`")

    new_node_in_run = node.clone(NodeClonePolicy.NODE_TO_RUN, override_finished_state=False)

    return node_in_run, new_node_in_run


def remove_auto_run_disabled(node: Node):
    """
    Trim the subnodes the way that if there is no need to run a subnode and it is not auto runnable, ignore it.
    """
    node_ids_to_remove = set()
    for sub_node in traverse_in_order(node):
        if (not sub_node.auto_run or not sub_node.auto_run_enabled) and not NodeRunningStatus.is_succeeded(sub_node.node_running_status):
            node_ids_to_remove.add(sub_node._id)
        for input in sub_node.inputs:   # pylint: disable=redefined-builtin
            for input_reference in input.input_references:
                if input_reference.node_id in node_ids_to_remove:
                    node_ids_to_remove.add(sub_node._id)

    if len(node_ids_to_remove) == 0:
        return

    sub_nodes_parameter = node.get_parameter_by_name('_nodes', throw=False)
    if not sub_nodes_parameter:
        logger.warning("remove_auto_run_disabled(..): are we supposed to be here?")
        return
    sub_nodes = sub_nodes_parameter.value.value

    sub_nodes_parameter.value.value = list(filter(lambda sn: sn._id not in node_ids_to_remove, sub_nodes))


def calc_status_to_node_ids(node: Optional[Node]) -> Dict[str, Set[ObjectId]]:
    """
    Make a map node_running_status to list of ids.
    """
    res: Dict[str, Set[ObjectId]] = defaultdict(set)
    if not node:
        return res
    for sub_node in node.get_sub_nodes():
        res[sub_node.node_running_status].add(sub_node._id)
    return res


def reset_nodes(node: Node):
    """
    Reset statuses of the sub-nodes as well as logs and outputs
    """
    for sub_node in node.get_sub_nodes():
        if NodeRunningStatus.is_non_changeable(sub_node.node_running_status):
            continue
        sub_node.node_running_status = NodeRunningStatus.READY
        for resource in sub_node.outputs + sub_node.logs:
            resource.values = []
        sub_node._cached_node = None
