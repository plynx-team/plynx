import logging
import time
from collections import defaultdict
from plynx.constants import ParameterTypes
from plynx.db.node import Node, Parameter
from plynx.db.validation_error import ValidationError
from plynx.constants import NodeRunningStatus, ValidationTargetType, ValidationCode, SpecialNodeId, Collections
from plynx.utils.common import to_object_id
import plynx.base.executor
import plynx.utils.executor
import plynx.db.node_collection_manager
import plynx.db.node_cache_manager
import plynx.db.run_cancellation_manager


node_collection_manager = plynx.db.node_collection_manager.NodeCollectionManager(collection=Collections.RUNS)
run_cancellation_manager = plynx.db.run_cancellation_manager.RunCancellationManager()
node_cache_manager = plynx.db.node_cache_manager.NodeCacheManager()

_GRAPH_ITERATION_SLEEP = 1
_WAIT_STATUS_BEFORE_FAILED = {
    NodeRunningStatus.RUNNING,
    NodeRunningStatus.IN_QUEUE,
    NodeRunningStatus.FAILED_WAITING,
}
_ACTIVE_WAITING_TO_STOP = {
    NodeRunningStatus.FAILED_WAITING,
    NodeRunningStatus.CANCELED,
}


class DAG(plynx.base.executor.BaseExecutor):
    """ Main graph scheduler.

    Args:
        node_dict (dict)

    """
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

        self._node_running_status = NodeRunningStatus.READY

        for node in self.subnodes:
            node_id = node._id
            if node_id == SpecialNodeId.INPUT:
                updated_resources_count = 0
                for output in node.outputs:
                    for input in self.node.inputs:
                        if input.name == output.name:
                            updated_resources_count += 1
                            output.values = input.values
                if updated_resources_count != len(self.node.inputs):
                    raise Exception('Used {} inputs for {} outputs'.format(updated_resources_count, len(self.node.inputs)))

            # ignore nodes in finished statuses
            if NodeRunningStatus.is_finished(node.node_running_status) and node_id != SpecialNodeId.OUTPUT:
                continue
            dependency_index = 0
            for node_input in node.inputs:
                for input_reference in node_input.input_references:
                    dep_node_id = to_object_id(input_reference.node_id)
                    self.node_id_to_dependents[dep_node_id].add(node_id)
                    if not NodeRunningStatus.is_finished(self.node_id_to_node[dep_node_id].node_running_status):
                        dependency_index += 1

            if not NodeRunningStatus.is_finished(node.node_running_status):
                self.uncompleted_nodes_count += 1
            self.dependency_index_to_node_ids[dependency_index].add(node_id)
            self.node_id_to_dependency_index[node_id] = dependency_index

        self.monitoring_node_ids = set()

        if self.uncompleted_nodes_count == 0:
            self._node_running_status = NodeRunningStatus.SUCCESS

    def finished(self):
        if self._node_running_status in _ACTIVE_WAITING_TO_STOP:
            # wait for the rest of the running jobs to finish
            # check running status of each of the nodes
            for node in self.subnodes:
                if node.node_running_status in _WAIT_STATUS_BEFORE_FAILED:
                    return False

            # set status to FAILED
            if self._node_running_status == NodeRunningStatus.FAILED_WAITING:
                self._node_running_status = NodeRunningStatus.FAILED
            return True
        return self._node_running_status in {NodeRunningStatus.SUCCESS, NodeRunningStatus.FAILED, NodeRunningStatus.CANCELED}

    def pop_jobs(self):
        """Get a set of nodes with satisfied dependencies"""
        res = []
        logging.info("Pop jobs")

        for running_node_dict in node_collection_manager.get_db_objects_by_ids(self.monitoring_node_ids):
            # check status
            if NodeRunningStatus.is_finished(running_node_dict['node_running_status']):
                node = Node.from_dict(running_node_dict)
                self.update_node(node)
                self.monitoring_node_ids.remove(node._id)

        if NodeRunningStatus.is_failed(self._node_running_status):
            logging.info("Job in DAG failed, pop_jobs will return []")
            return res

        cached_nodes = []
        for node_id in self.dependency_index_to_node_ids[0]:
            """Get the node and init its inputs, i.e. filling its resource_ids"""
            orig_node = self.node_id_to_node[node_id]
            for node_input in orig_node.inputs:
                for input_reference in node_input.input_references:
                    node_input.values.extend(
                        self.node_id_to_node[to_object_id(input_reference.node_id)].get_output_by_name(
                            input_reference.output_id
                        ).values
                    )
            orig_node.node_running_status = NodeRunningStatus.IN_QUEUE
            node = orig_node.copy()

            if DAG._cacheable(node):
                try:
                    cache = node_cache_manager.get(node)
                    if cache:
                        node.node_running_status = NodeRunningStatus.RESTORED
                        node.outputs = cache.outputs
                        node.logs = cache.logs
                        node.cache_url = '/runs/{}?nid={}'.format(
                            str(cache.run_id),
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
        if cached_nodes:
            node.save(collection=Collections.RUNS)

        return res

    def update_node(self, node):
        dest_node = self.node_id_to_node[node._id]
        if node.node_running_status == NodeRunningStatus.SUCCESS \
                and dest_node.node_running_status != node.node_running_status \
                and DAG._cacheable(node):
            node_cache_manager.post(node, self.node._id)

        if dest_node.node_running_status == node.node_running_status:
            return

        self._set_node_status(node._id, node.node_running_status)
        # TODO smarter copy
        dest_node.parameters = node.parameters
        dest_node.logs = node.logs
        dest_node.outputs = node.outputs
        dest_node.cache_url = node.cache_url

    def _set_node_status(self, node_id, node_running_status):
        node = self.node_id_to_node[node_id]
        node.node_running_status = node_running_status

        logging.info("Node running status {} {}".format(node_running_status, node.title))

        if node_running_status == NodeRunningStatus.FAILED:
            # TODO optional cancel based on parameter
            self.kill()
            self._node_running_status = NodeRunningStatus.FAILED_WAITING

        if node_running_status in {NodeRunningStatus.SUCCESS, NodeRunningStatus.RESTORED}:
            for dependent_node_id in self.node_id_to_dependents[node_id]:
                dependent_node = self.node_id_to_node[dependent_node_id]
                prev_dependency_index = self.node_id_to_dependency_index[dependent_node_id]

                removed_dependencies = 0
                for node_input in dependent_node.inputs:
                    for input_reference in node_input.input_references:
                        if to_object_id(input_reference.node_id) == to_object_id(node_id):
                            removed_dependencies += 1
                dependency_index = prev_dependency_index - removed_dependencies

                self.dependency_index_to_node_ids[prev_dependency_index].remove(dependent_node_id)
                self.dependency_index_to_node_ids[dependency_index].add(dependent_node_id)
                self.node_id_to_dependency_index[dependent_node_id] = dependency_index
            self.uncompleted_nodes_count -= 1

        if self.uncompleted_nodes_count == 0 and not NodeRunningStatus.is_failed(self._node_running_status):
            self._node_running_status = NodeRunningStatus.SUCCESS

    @staticmethod
    def _cacheable(node):
        for parameter in node.parameters:
            if parameter.name == '_cacheable':
                return parameter.value
        return False

    @classmethod
    def get_default_node(cls, is_workflow):
        node = super().get_default_node(is_workflow)
        if not is_workflow:
            node.parameters.append(
                Parameter.from_dict({
                    'name': '_cacheable',
                    'parameter_type': ParameterTypes.BOOL,
                    'value': False,
                    'mutable_type': False,
                    'publicable': False,
                    'removable': False,
                })
            )
        node.parameters.append(
            Parameter.from_dict({
                'name': '_timeout',
                'parameter_type': ParameterTypes.INT,
                'value': 600,
                'mutable_type': False,
                'publicable': True,
                'removable': False
            })
        )
        node.title = 'New DAG workflow'
        return node

    def _execute_node(self, node):
        if NodeRunningStatus.is_finished(node.node_running_status):     # NodeRunningStatus.SPECIAL
            return
        node.author = self.node.author                                  # Change it to the author that runs it
        node.save(collection=Collections.RUNS)

        self.monitoring_node_ids.add(node._id)

    def run(self):
        while not self.finished():
            new_jobs = self.pop_jobs()
            if len(new_jobs) == 0:
                time.sleep(_GRAPH_ITERATION_SLEEP)
                continue

            for node in new_jobs:
                self._execute_node(node)

        is_succeeded = NodeRunningStatus.is_succeeded(self._node_running_status)
        if is_succeeded:
            for node in self.subnodes:
                if node._id != SpecialNodeId.OUTPUT:
                    continue
                updated_resources_count = 0
                for output in self.node.outputs:
                    for input in node.inputs:
                        if input.name == output.name:
                            output.values = input.values
                            updated_resources_count += 1
                            break
                if updated_resources_count != len(node.inputs):
                    raise Exception('Used {} inputs for {} outputs'.format(updated_resources_count, len(node.inputs)))
        return self._node_running_status

    def kill(self):
        """Force to kill the process.

        The reason can be the fact it was working too long or parent exectuter canceled it.
        """
        self._node_running_status = NodeRunningStatus.CANCELED
        for node_id in list(self.monitoring_node_ids):
            run_cancellation_manager.cancel_run(node_id)

    def validate(self):
        validation_error = super().validate()
        if validation_error:
            return validation_error

        violations = []
        sub_nodes = self.node.get_parameter_by_name('_nodes').value.value

        if len(sub_nodes) == 0:
            violations.append(
                ValidationError(
                    target=ValidationTargetType.GRAPH,
                    object_id=str(self.node._id),
                    validation_code=ValidationCode.EMPTY_GRAPH
                ))

        for node in sub_nodes:
            node_violation = plynx.utils.executor.materialize_executor(node.to_dict()).validate()
            if node_violation:
                violations.append(node_violation)

        if len(violations) == 0:
            return None

        return ValidationError(
            target=ValidationTargetType.GRAPH,
            object_id=str(self.node._id),
            validation_code=ValidationCode.IN_DEPENDENTS,
            children=violations
        )
