"""An executor for the DAGs based on python backend."""
import logging
import multiprocessing
import queue
import traceback
import uuid
from typing import List

import plynx.plugins.executors.dag
import plynx.utils.executor
from plynx.constants import Collections, NodeRunningStatus
from plynx.db.node import Node
from plynx.utils import node_utils
from plynx.utils.common import to_object_id

POOL_SIZE = 3


def worker_main(job_run_queue: queue.Queue, job_complete_queue: queue.Queue):
    """Main threaded function that serves Operations."""
    logging.info("Created pool worker")
    while True:
        node = job_run_queue.get()
        executor = plynx.utils.executor.materialize_executor(node)

        try:
            # TODO support async executors
            executor.launch()
        except Exception:   # pylint: disable=broad-except
            error_str = traceback.format_exc()
            logging.error(f"Job failed with traceback: {error_str}")
            node.node_running_status = NodeRunningStatus.FAILED

            err_filename = str(uuid.uuid4())
            with plynx.utils.file_handler.open(err_filename, "w") as f:
                f.write(error_str)
            output = node.get_log_by_name(name="traceback")
            output.values = [err_filename]
            logging.error(f"Wrote to logs: {err_filename}")
        else:
            node.node_running_status = NodeRunningStatus.SUCCESS
        job_complete_queue.put(node)
        logging.info(f"worker_main: added node {node.title} on the job_complete_queue queue")

    logging.info("Deleted pool worker")


class DAGParallel(plynx.plugins.executors.dag.DAG):
    """ Python DAG scheduler.

    Args:
        node_dict (dict)
    """
    IS_GRAPH = True
    GRAPH_ITERATION_SLEEP = 0

    def __init__(self, node: Node):
        super().__init__(node)

        self.job_run_queue: queue.Queue = queue.Queue()
        self.job_complete_queue: queue.Queue = queue.Queue()

        self.worker_pool = multiprocessing.pool.ThreadPool(
            POOL_SIZE, worker_main, (
                self.job_run_queue,
                self.job_complete_queue,
            )
        )

    def pop_jobs(self) -> List[Node]:
        """Get a set of nodes with satisfied dependencies"""
        assert self.node, "Attribute `node` is undefined"
        res: List[Node] = []

        num_completed_jobs = 0
        while not self.job_complete_queue.empty():
            try:
                node = self.job_complete_queue.get_nowait()
                logging.info(f"pop_jobs: run update {node.title}: start")
                self.update_node(node)
                logging.info(f"pop_jobs: run update {node.title}: finish")
                num_completed_jobs += 1
            except queue.Empty:
                logging.warning("Queue is empty")
                break

        if NodeRunningStatus.is_failed(self._node_running_status):
            if self._node_running_status != NodeRunningStatus.FAILED_WAITING:
                logging.info(f"Job in DAG failed with status {self._node_running_status}, pop_jobs will return []")
            return res

        for node_id in self.dependency_index_to_node_ids[0]:
            # Get the node and init its inputs, i.e. filling its resource_ids
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

        if num_completed_jobs > 0:
            self.node.save(collection=Collections.RUNS, force=True)

        return res

    def _execute_node(self, node: Node):
        assert self.node, "Attribute `node` is undefined"
        if NodeRunningStatus.is_finished(node.node_running_status):     # NodeRunningStatus.SPECIAL
            return

        logging.info(f'Execute {node} {node.title}')
        node.node_running_status = NodeRunningStatus.RUNNING
        self.node.save(collection=Collections.RUNS)
        # TODO somehow optimize `update_node`?
        # If not copy but original sent, the dependencies list won't be updated
        self.job_run_queue.put(node.copy())

    def kill(self):
        """Force to kill the process.

        The reason can be the fact it was working too long or parent exectuter canceled it.
        """
        logging.info("Received kill request")
        self._node_running_status = NodeRunningStatus.CANCELED
        self.worker_pool.terminate()

    def finished(self) -> bool:
        """Return True or False depending on the running status of the DAG."""
        # TODO wait for the canceled nodes to complete
        return self._node_running_status in {NodeRunningStatus.SUCCESS, NodeRunningStatus.FAILED, NodeRunningStatus.CANCELED}


class DAG(plynx.plugins.executors.dag.DAG):
    """Base Executor class"""
    IS_GRAPH: bool = True

    def __init__(self, node: Node):
        super().__init__(node)
        self.job_run_queue: queue.Queue = queue.Queue()
        self.job_complete_queue: queue.Queue = queue.Queue()
        self.worker_pool = None

    def kill(self):
        """Force to kill the process.

        The reason can be the fact it was working too long or parent exectuter canceled it.
        """
        logging.info("Received kill request")
        self._node_running_status = NodeRunningStatus.CANCELED
        self.job_complete_queue.put(NodeRunningStatus.CANCELED)

    def init_executor(self):
        """Initialize environment for the executor"""
        pool_size = 1
        self.worker_pool = multiprocessing.pool.ThreadPool(
            pool_size, worker_main, (
                self.job_run_queue,
                self.job_complete_queue,
            )
        )

    def clean_up_executor(self):
        """Clean up the environment created by executor"""
        if self.worker_pool:
            self.worker_pool.terminate()
        self.worker_pool = None

    def _apply_inputs(self, node):
        for node_input in node.inputs:
            for input_reference in node_input.input_references:
                node_input.values.extend(
                    self.node_id_to_node[to_object_id(input_reference.node_id)].get_output_by_name(
                        input_reference.output_id
                    ).values
                )

    def run(self, preview: bool = False) -> str:
        """Main execution function.
        """
        assert self.node, "Attribute `node` is unassigned"
        if preview:
            raise Exception("`preview` is not supported for the DAG")

        for sub_node in node_utils.traverse_in_order(self.node):
            if NodeRunningStatus.is_finished(sub_node.node_running_status):
                continue
            self._apply_inputs(sub_node)
            sub_node.node_running_status = NodeRunningStatus.RUNNING
            self.node.save(collection=Collections.RUNS, force=True)

            # Run
            self.job_run_queue.put(sub_node.copy())
            new_node = self.job_complete_queue.get()

            # In case something else is on the queue (i.e. canceled)
            if isinstance(new_node, Node):
                self.update_node(new_node)

            if NodeRunningStatus.is_finished(self._node_running_status):
                prev_status = self._node_running_status
                self._node_running_status = prev_status
                break
            self.node.save(collection=Collections.RUNS, force=True)

        if self._node_running_status == NodeRunningStatus.FAILED_WAITING:
            self._node_running_status = NodeRunningStatus.FAILED
        return self._node_running_status
