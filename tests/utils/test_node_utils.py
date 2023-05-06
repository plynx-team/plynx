"""Test the node utils."""
from typing import Dict

from tests.plugins.executors.test_python_dag import create_graph_flow

from plynx.constants import NodeRunningStatus
from plynx.db.node import Node
from plynx.plugins.executors.python.dag import DAG
from plynx.utils import node_utils
from plynx.utils.common import ObjectId


def test_traverse():
    flow_node = create_graph_flow()

    seen_nodes = set()
    for node in node_utils.traverse_in_order(flow_node):
        assert node._id not in seen_nodes, f"Already have seen the node with id {node._id}"

        for input_ in node.inputs:
            for input_ref in input_.input_references:
                assert input_ref.node_id in seen_nodes, f"Input reference to node {input_ref.node_id} is not seen yet"
        seen_nodes.add(node._id)


def test_arrange_auto_layout():
    flow_node = create_graph_flow()
    node_utils.arrange_auto_layout(flow_node)

    prev_x: Dict[ObjectId, int] = {}
    for node in node_utils.traverse_in_order(flow_node):
        assert node.x is not None
        assert node.y is not None
        assert node.x >= 0
        assert node.y >= 0

        for input_ in node.inputs:
            for input_ref in input_.input_references:
                assert prev_x[input_ref.node_id] < node.x, f"Node {input_ref.node_id} should be on the left of {node._id}"
        prev_x[node._id] = node.x


def test_completed():
    flow_node = create_graph_flow()
    executor = DAG(flow_node)
    executor.run()

    stats = node_utils.calc_status_to_node_ids(flow_node)
    assert len(stats[NodeRunningStatus.SUCCESS]) == 4, "There should be 4 successful nodes"

    flow_node.node_running_status = NodeRunningStatus.READY
    for sub_node in flow_node.get_sub_nodes():
        if sub_node.title == "C":
            sub_node.node_running_status = NodeRunningStatus.READY
            sub_node.auto_run = False
            break

    node_utils.remove_auto_run_disabled(flow_node)
    stats = node_utils.calc_status_to_node_ids(flow_node)
    assert len(stats[NodeRunningStatus.SUCCESS]) == 2, "There should be 2 successful nodes because C was reverted"


def test_augment_node_with_cache():
    flow_node_a = create_graph_flow()
    flow_node_b = Node.from_dict(flow_node_a.to_dict())

    # Modify the last node in the second flow. It looks like a new one.
    flow_node_b.get_sub_nodes()[-1]._id = ObjectId()
    # Fill the outputs by running the executor
    executor = DAG(flow_node_b)
    executor.run()

    node_utils.augment_node_with_cache(flow_node_a, flow_node_b)

    num_of_cached = 0
    for subnode_a in flow_node_a.get_sub_nodes():
        if subnode_a._cached_node:
            num_of_cached += 1

    assert num_of_cached == len(flow_node_a.get_sub_nodes()) - 1, "Did not find all the nodes"


def test_traverse_left_join():
    flow_node_a = create_graph_flow()
    flow_node_b = Node.from_dict(flow_node_a.to_dict())

    node_count = 0
    for subnode_a, subnode_b in node_utils.traverse_left_join(flow_node_a, flow_node_b):
        assert subnode_a and subnode_b, "One of the nodes was not found"
        node_count += 1

    assert node_count == len(flow_node_a.get_sub_nodes()), "Did not traverse all the nodes (or visited more than once)"

    # Modify the last node in the second flow. It looks like a new one.
    flow_node_b.get_sub_nodes()[-1]._id = ObjectId()

    found_count = 0
    not_found_count = 0
    for subnode_a, subnode_b in node_utils.traverse_left_join(flow_node_a, flow_node_b):
        assert subnode_a, "The node was not found"
        if subnode_b:
            found_count += 1
        else:
            not_found_count += 1

    assert found_count == len(flow_node_a.get_sub_nodes()) - 1, "Did not find all the nodes"
    assert not_found_count == 1, "Did not find all the nodes"
