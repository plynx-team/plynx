import logging
from collections import defaultdict
from plynx.db import Graph, NodeCacheManager
from plynx.constants import NodeRunningStatus, GraphRunningStatus
from plynx.graph.base_nodes import NodeCollection
from plynx.utils.common import to_object_id
from plynx.utils.config import get_web_config


class GraphScheduler(object):
    """ Main graph scheduler.

    It works with a single db.graph.Graph object.
    GraphScheduler loads the Graph from DB.
    It determines Nodes to be executed.

    Args:
        graph (str or Graph)

    """
    node_cache_manager = NodeCacheManager()
    WEB_CONFIG = get_web_config()

    def __init__(self, graph, node_collection=None):
        if isinstance(graph, Graph):
            self.graph_id = graph._id
            self.graph = graph
        else:
            self.graph_id = graph
            self.graph = Graph.load(self.graph_id)

        self.node_id_to_node = {
            node._id: node for node in self.graph.nodes
        }

        # number of dependencies to ids
        self.dependency_index_to_node_ids = defaultdict(lambda: set())
        self.node_id_to_dependents = defaultdict(lambda: set())
        self.node_id_to_dependency_index = defaultdict(lambda: 0)
        self.uncompleted_nodes_count = 0
        if node_collection:
            self.node_collection = node_collection
        else:
            self.node_collection = NodeCollection()

        for node in self.graph.nodes:
            # ignore nodes in finished statuses
            if node.node_running_status in {
                    NodeRunningStatus.SUCCESS,
                    NodeRunningStatus.FAILED,
                    NodeRunningStatus.STATIC,
                    NodeRunningStatus.RESTORED,
                    NodeRunningStatus.CANCELED}:
                continue
            node_id = node._id
            dependency_index = 0
            for node_input in node.inputs:
                for input_value in node_input.values:
                    parent_node_id = to_object_id(input_value.node_id)
                    self.node_id_to_dependents[parent_node_id].add(node_id)
                    if self.node_id_to_node[parent_node_id].node_running_status not in {
                            NodeRunningStatus.SUCCESS,
                            NodeRunningStatus.FAILED,
                            NodeRunningStatus.STATIC,
                            NodeRunningStatus.RESTORED,
                            NodeRunningStatus.CANCELED}:
                        dependency_index += 1

            if node.node_running_status not in {
                    NodeRunningStatus.SUCCESS,
                    NodeRunningStatus.FAILED,
                    NodeRunningStatus.STATIC,
                    NodeRunningStatus.RESTORED,
                    NodeRunningStatus.CANCELED}:
                self.uncompleted_nodes_count += 1
            self.dependency_index_to_node_ids[dependency_index].add(node_id)
            self.node_id_to_dependency_index[node_id] = dependency_index

    def finished(self):
        return self.graph.graph_running_status in {GraphRunningStatus.SUCCESS, GraphRunningStatus.FAILED, GraphRunningStatus.CANCELED}

    def pop_jobs(self):
        """Get a set of nodes with satisfied dependencies"""
        res = []
        cached_nodes = []
        for node_id in self.dependency_index_to_node_ids[0]:
            node = self._get_node_with_inputs(node_id).copy()
            if GraphScheduler._cacheable(node):
                try:
                    cache = GraphScheduler.node_cache_manager.get(node, self.graph.author)
                    if cache:
                        node.node_running_status = NodeRunningStatus.RESTORED
                        node.outputs = cache.outputs
                        node.logs = cache.logs
                        node.cache_url = '{}/graphs/{}?nid={}'.format(
                            GraphScheduler.WEB_CONFIG.endpoint.rstrip('/'),
                            str(cache.graph_id),
                            str(cache.node_id),
                        )
                        cached_nodes.append(node)
                        continue
                except Exception as err:
                    logging.exception("Unable to update cache: `{}`".format(err))
            job = self.node_collection.make_job(node)
            res.append(job)
        del self.dependency_index_to_node_ids[0]

        for node in cached_nodes:
            self.update_node(node)

        return res

    def update_node(self, node):
        dest_node = self.node_id_to_node[node._id]
        if node.node_running_status == NodeRunningStatus.SUCCESS \
                and dest_node.node_running_status != node.node_running_status \
                and GraphScheduler._cacheable(node):
            GraphScheduler.node_cache_manager.post(node, self.graph_id, self.graph.author)

        if dest_node.node_running_status == node.node_running_status:
            return

        self._set_node_status(node._id, node.node_running_status)
        # TODO smarter copy
        dest_node.logs = node.logs
        dest_node.outputs = node.outputs
        dest_node.cache_url = node.node_running_status

        self.graph.save(force=True)

    def _set_node_status(self, node_id, node_running_status):
        node = self.node_id_to_node[node_id]
        node.node_running_status = node_running_status

        if node_running_status == NodeRunningStatus.FAILED:
            self.graph.graph_running_status = GraphRunningStatus.FAILED

        if node_running_status in {NodeRunningStatus.SUCCESS, NodeRunningStatus.FAILED, NodeRunningStatus.RESTORED}:
            for dependent_node_id in self.node_id_to_dependents[node_id]:
                dependent_node = self.node_id_to_node[dependent_node_id]
                prev_dependency_index = self.node_id_to_dependency_index[dependent_node_id]

                removed_dependencies = 0
                for node_input in dependent_node.inputs:
                    for input_value in node_input.values:
                        if to_object_id(input_value.node_id) == to_object_id(node_id):
                            removed_dependencies += 1
                dependency_index = prev_dependency_index - removed_dependencies

                self.dependency_index_to_node_ids[prev_dependency_index].remove(dependent_node_id)
                self.dependency_index_to_node_ids[dependency_index].add(dependent_node_id)
                self.node_id_to_dependency_index[dependent_node_id] = dependency_index
            self.uncompleted_nodes_count -= 1

        if self.uncompleted_nodes_count == 0 and self.graph.graph_running_status != GraphRunningStatus.FAILED:
            self.graph.graph_running_status = GraphRunningStatus.SUCCESS

        # self.graph.save()

    def _get_node_with_inputs(self, node_id):
        """Get the node and init its inputs, i.e. filling its resource_ids"""
        res = self.node_id_to_node[node_id]
        for node_input in res.inputs:
            for value in node_input.values:
                value.resource_id = self.node_id_to_node[to_object_id(value.node_id)].get_output_by_name(
                    value.output_id
                ).resource_id
        return res

    @staticmethod
    def _cacheable(node):
        for parameter in node.parameters:
            if parameter.name == 'cacheable':
                return parameter.value
        return False
