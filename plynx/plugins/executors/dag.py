import logging
import time
from collections import defaultdict
from plynx.constants import ParameterTypes
from plynx.db.node import Node, Parameter, Output
from plynx.constants import JobReturnStatus, NodeRunningStatus, GraphRunningStatus
from plynx.utils.common import to_object_id
from plynx.plugins.executors import BaseExecutor
from plynx.db.node_collection_manager import NodeCollectionManager

node_collection_manager = NodeCollectionManager(collection='runs')

_GRAPH_ITERATION_SLEEP = 1


class DAG(BaseExecutor):
    """ Main graph scheduler.

    It works with a single db.graph.Graph object.
    GraphScheduler loads the Graph from DB.
    It determines Nodes to be executed.

    Args:
        graph (str or Graph)

    """
    ALIAS = 'DAG'
    IS_GRAPH = True

    def __init__(self, node_dict):
        super(DAG, self).__init__(node_dict)

        self.subnodes = None
        # TODO make a function to look for parameter
        for parameter in self.node.parameters:
            if parameter.name == '_nodes':
                self.subnodes = parameter.value.value

        assert self.subnodes is not None, 'Could not find subnodes'

        self.node_id_to_node = {
            node._id: node for node in self.subnodes
        }

        # number of dependencies to ids
        self.dependency_index_to_node_ids = defaultdict(lambda: set())
        self.node_id_to_dependents = defaultdict(lambda: set())
        self.node_id_to_dependency_index = defaultdict(lambda: 0)
        self.uncompleted_nodes_count = 0

        for node in self.subnodes:
            # ignore nodes in finished statuses
            if NodeRunningStatus.is_finished(node.node_running_status):
                continue
            node_id = node._id
            dependency_index = 0
            for node_input in node.inputs:
                for input_value in node_input.values:
                    dep_node_id = to_object_id(input_value.node_id)
                    self.node_id_to_dependents[dep_node_id].add(node_id)
                    if not NodeRunningStatus.is_finished(self.node_id_to_node[dep_node_id].node_running_status):
                        dependency_index += 1

            if not NodeRunningStatus.is_finished(node.node_running_status):
                self.uncompleted_nodes_count += 1
            self.dependency_index_to_node_ids[dependency_index].add(node_id)
            self.node_id_to_dependency_index[node_id] = dependency_index

        self.monitoring_node_ids = set()

    def finished(self):
        if self.node.node_running_status == NodeRunningStatus.FAILED_WAITING:
            # wait for the rest of the running jobs to finish
            # check running status of each of the nodes
            for node in self.subnodes:
                if node.node_running_status == NodeRunningStatus.RUNNING:
                    return False
            # set status to FAILED
            self.node.node_running_status = NodeRunningStatus.FAILED
            self.node.save(force=True)
            return True
        return self.node.node_running_status in {NodeRunningStatus.SUCCESS, NodeRunningStatus.FAILED, NodeRunningStatus.CANCELED}

    def pop_jobs(self):
        """Get a set of nodes with satisfied dependencies"""
        res = []
        if NodeRunningStatus.is_failed(self.node.node_running_status):
            return res

        for running_node_dict in node_collection_manager.get_db_nodes_by_ids(self.monitoring_node_ids):
            # check status
            if NodeRunningStatus.is_finished(running_node_dict['node_running_status']):
                node = Node.from_dict(running_node_dict)
                self.update_node(node)
                self.monitoring_node_ids.remove(node._id)

        cached_nodes = []
        for node_id in self.dependency_index_to_node_ids[0]:
            node = self._get_node_with_inputs(node_id).copy()
            if DAG._cacheable(node) and False:  # !!! _cacheable is broken
                try:
                    cache = self.node_cache_manager.get(node, self.graph.author)
                    if cache:
                        node.node_running_status = NodeRunningStatus.RESTORED
                        node.outputs = cache.outputs
                        node.logs = cache.logs
                        node.cache_url = '{}/graphs/{}?nid={}'.format(
                            self.WEB_CONFIG.endpoint.rstrip('/'),
                            str(cache.graph_id),
                            str(cache.node_id),
                        )
                        cached_nodes.append(node)
                        continue
                except Exception as err:
                    logging.exception("Unable to update cache: `{}`".format(err))
            res.append(node)
        del self.dependency_index_to_node_ids[0]

        for node in cached_nodes:
            self.update_node(node)

        return res

    def update_node(self, node):
        dest_node = self.node_id_to_node[node._id]
        """
        if node.node_running_status == NodeRunningStatus.SUCCESS \
                and dest_node.node_running_status != node.node_running_status \
                and GraphScheduler._cacheable(node):
            GraphScheduler.node_cache_manager.post(node, self.graph_id, self.graph.author)
        """
        if dest_node.node_running_status == node.node_running_status:
            return

        self._set_node_status(node._id, node.node_running_status)
        # TODO smarter copy
        dest_node.logs = node.logs
        dest_node.outputs = node.outputs
        dest_node.cache_url = node.cache_url

        # self.graph.save(force=True)

    def _set_node_status(self, node_id, node_running_status):
        node = self.node_id_to_node[node_id]
        node.node_running_status = node_running_status

        if node_running_status == NodeRunningStatus.FAILED:
            self.node.node_running_status = NodeRunningStatus.FAILED_WAITING

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

        if self.uncompleted_nodes_count == 0 and not NodeRunningStatus.is_failed(self.node.node_running_status):
            self.node.node_running_status = GraphRunningStatus.SUCCESS

        self.node.save(collection='runs')

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
            if parameter.name == '_cacheable':
                return parameter.value
        return False

    @classmethod
    def get_default_node(cls):
        node = Node()
        node.parameters = [
            Parameter.from_dict({
                'name': '_nodes',
                'parameter_type': ParameterTypes.LIST_NODE,
                'value': [],
                'mutable_type': False,
                'publicable': False,
                'removable': False,
                }
            ),
            Parameter.from_dict({
                'name': '_cacheable',
                'parameter_type': ParameterTypes.BOOL,
                'value': False,
                'mutable_type': False,
                'publicable': False,
                'removable': False,
            }),
            Parameter.from_dict({
                'name': '_timeout',
                'parameter_type': ParameterTypes.INT,
                'value': 600,
                'mutable_type': False,
                'publicable': True,
                'removable': False
            }),
        ]
        return node

    def execute_node(self, node):
        node.save(collection='runs')

        self.monitoring_node_ids.add(node._id)

    def run(self):
        self.node.save(collection='runs')
        while not self.finished():
            new_jobs = self.pop_jobs()
            if len(new_jobs) == 0:
                time.sleep(_GRAPH_ITERATION_SLEEP)
                continue

            for node in new_jobs:
                self.execute_node(node)

        return JobReturnStatus.SUCCESS if NodeRunningStatus.is_succeeded(self.node.node_running_status) else JobReturnStatus.FAILED
