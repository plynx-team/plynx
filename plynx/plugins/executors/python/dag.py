import logging
import queue
import time
import types
import cloudpickle
import multiprocessing
import traceback
import uuid
from collections import defaultdict
from plynx.constants import ParameterTypes
from plynx.db.node import Node, Parameter
from plynx.db.validation_error import ValidationError
from plynx.constants import NodeRunningStatus, ValidationTargetType, ValidationCode, SpecialNodeId, Collections
from plynx.utils.common import to_object_id
import plynx.base.executor
import plynx.utils.executor
import plynx.utils.remote
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
POOL_SIZE = 3


def materialize_fn(fn_str):
    fn_bytes = bytes.fromhex(fn_str)
    fn2 = cloudpickle.loads(fn_bytes)
    #fn2 = types.FunctionType(code, globals(), "some_func_name")
    return fn2


def prep_args(node):
    args = {}
    for input in node.inputs:
        args[input.name] = input.values if input.is_array else input.values[0]

    # TODO smater way to determine what parameters to pass
    visible_parameters = filter(lambda param: param.widget is not None, node.parameters)
    args.update(
        plynx.plugins.executors.local.prepare_parameters_for_python(visible_parameters)
    )
    return args


def assign_outputs(node, output_dict):
    for key, value in output_dict.items():
        node_output = node.get_output_by_name(key)
        node_output.values = value if node_output.is_array else [value]


def worker_main(job_run_queue, job_complete_queue):
    logging.info("Created pool worker")
    while True:
        node = job_run_queue.get()

        pickled_fn_parameter = node.get_parameter_by_name("_pickled_fn")

        fn = materialize_fn(pickled_fn_parameter.value)
        try:
            res = fn(**prep_args(node))
        except Exception as e:
            error_str = traceback.format_exc()
            logging.error(f"Job failed with traceback: {error_str}")
            node.node_running_status = NodeRunningStatus.FAILED

            err_filename = str(uuid.uuid4())
            with plynx.utils.remote.open(err_filename, "w") as f:
                f.write(error_str)
            output = node.get_log_by_name(name="traceback")
            output.values = [err_filename]
            logging.error(f"Wrote to logs: {err_filename}")
        else:
            assign_outputs(node, res)
            node.node_running_status = NodeRunningStatus.SUCCESS
        job_complete_queue.put(node)

    logging.info("Deleted pool worker")

class DAG(plynx.plugins.executors.dag.DAG):
    """ Python DAG scheduler.

    Args:
        node_dict (dict)

    """
    IS_GRAPH = True

    def __init__(self, node_dict):
        super(DAG, self).__init__(node_dict)
        self.job_run_queue = multiprocessing.Queue()
        self.job_complete_queue = multiprocessing.Queue()
        self.worker_pool = multiprocessing.Pool(POOL_SIZE, worker_main, (self.job_run_queue, self.job_complete_queue))


    def pop_jobs(self):
        """Get a set of nodes with satisfied dependencies"""
        res = []
        logging.info("Pop jobs")

        completed_jobs = []
        while not self.job_complete_queue.empty():
            try:
                node = self.job_complete_queue.get_nowait()
                self.update_node(node)
            except queue.Empty:
                logging.warning("Raised Exception")
                break

        if NodeRunningStatus.is_failed(self._node_running_status):
            logging.info("Job in DAG failed, pop_jobs will return []")
            return res

        for node_id in self.dependency_index_to_node_ids[0]:
            """Get the node and init its inputs, i.e. filling its resource_ids"""
            node = self.node_id_to_node[node_id]
            for node_input in node.inputs:
                for input_reference in node_input.input_references:
                    node_input.values.extend(
                        self.node_id_to_node[to_object_id(input_reference.node_id)].get_output_by_name(
                            input_reference.output_id
                        ).values
                    )
            node.node_running_status = NodeRunningStatus.IN_QUEUE

            res.append(node)
        del self.dependency_index_to_node_ids[0]

        return res

    def _execute_node(self, node):
        if NodeRunningStatus.is_finished(node.node_running_status):     # NodeRunningStatus.SPECIAL
            return
        """
        node.author = self.node.author                                  # Change it to the author that runs it
        node.save(collection=Collections.RUNS)

        self.monitoring_node_ids.add(node._id)
        """
        logging.info(f'Execute {node}')
        node.node_running_status = NodeRunningStatus.RUNNING
        self.node.save(collection=Collections.RUNS)
        self.job_run_queue.put(node)


    """
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
    """

    def kill(self):
        """Force to kill the process.

        The reason can be the fact it was working too long or parent exectuter canceled it.
        """
        pass
        #raise NotImplementedError()
