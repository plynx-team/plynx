"""An executor for the DAGs based on python backend."""
import contextlib
import inspect
import logging
import multiprocessing
import os
import queue
import sys
import threading
import traceback
import uuid
from typing import Any, Callable, Dict, List

import cloudpickle

import plynx.plugins.executors.dag
from plynx.constants import Collections, NodeRunningStatus
from plynx.db.node import Node
from plynx.utils.common import to_object_id

stateful_init_mutex = threading.Lock()
stateful_class_registry = {}

POOL_SIZE = 3


def materialize_fn_or_cls(node: Node) -> Callable:
    """Unpickle the function"""

    pickled_fn_parameter = node.get_parameter_by_name("_pickled_fn", throw=False)
    code_parameter = node.get_parameter_by_name("_cmd", throw=False)
    assert not (pickled_fn_parameter and code_parameter), "`_pickled_fn` and `_cmd` cannot be both non-null"
    if pickled_fn_parameter:
        fn_str: str = pickled_fn_parameter.value

        func_bytes = bytes.fromhex(fn_str)
        func = cloudpickle.loads(func_bytes)
        return func
    elif code_parameter:
        code = code_parameter.value.value
        local_vars: Dict[str, Any] = {}
        exec(code, globals(), local_vars)   # pylint: disable=W0122
        return local_vars["operation"]
    raise ValueError("No function to materialize")


def prep_args(node: Node) -> Dict[str, Any]:
    """Pythonize inputs and parameters"""
    args = {}
    for input in node.inputs:   # pylint: disable=redefined-builtin
        args[input.name] = input.values if input.is_array else input.values[0]

    # TODO smater way to determine what parameters to pass
    visible_parameters = list(filter(lambda param: param.widget is not None, node.parameters))
    args.update(
        plynx.plugins.executors.local.prepare_parameters_for_python(visible_parameters)
    )
    return args


def assign_outputs(node: Node, output_dict: Dict[str, Any]):
    """Apply output_dict to node's outputs."""
    if not output_dict:
        return
    for key, value in output_dict.items():
        node_output = node.get_output_by_name(key)
        node_output.values = value if node_output.is_array else [value]


class redirect_to_plynx_logs:   # pylint: disable=invalid-name
    """Redirect stdout and stderr to standard PLynx Outputs"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, node: Node, stdout: str, stderr: str):
        self.stdout_filename = str(uuid.uuid4())
        self.stderr_filename = str(uuid.uuid4())

        self.stdout = stdout
        self.stderr = stderr

        self.node = node

        self.names_map = [
            (self.stdout_filename, self.stdout),
            (self.stderr_filename, self.stderr),
        ]

        self.stdout_file = None
        self.stderr_file = None

        self.stdout_redirect = None
        self.stderr_redirect = None

    def __enter__(self):
        self.stdout_file = open(self.stdout_filename, 'w')
        self.stderr_file = open(self.stderr_filename, 'w')

        self.stdout_redirect = contextlib.redirect_stdout(self.stdout_file)
        self.stderr_redirect = contextlib.redirect_stderr(self.stderr_file)

        self.stdout_redirect.__enter__()
        self.stderr_redirect.__enter__()

    def __exit__(self, *args):

        self.stdout_redirect.__exit__(*sys.exc_info())
        self.stderr_redirect.__exit__(*sys.exc_info())

        self.stdout_file.close()
        self.stderr_file.close()

        for filename, logs_name in self.names_map:
            if os.stat(filename).st_size > 0:
                with plynx.utils.file_handler.open(filename, "w") as f:
                    with open(filename) as fi:
                        f.write(fi.read())
                output = self.node.get_log_by_name(name=logs_name)
                output.values = [filename]


def worker_main(job_run_queue: queue.Queue, job_complete_queue: queue.Queue):
    """Main threaded function that serves Operations."""
    logging.info("Created pool worker")
    while True:
        node = job_run_queue.get()

        try:
            func = materialize_fn_or_cls(node)
            if inspect.isclass(func):
                with stateful_init_mutex:
                    if node.code_hash not in stateful_class_registry:
                        with redirect_to_plynx_logs(node, "init_stdout", "init_stderr"):
                            stateful_class_registry[node.code_hash] = func()
                    func = stateful_class_registry[node.code_hash]

            with redirect_to_plynx_logs(node, "stdout", "stderr"):
                res = func(**prep_args(node))

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
                self.update_node(node)
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
