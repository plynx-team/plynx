"""Main PLynx worker service and utils"""

import json
import logging
import socket
import sys
import threading
import time
import traceback
import uuid
from typing import Dict, Optional, Set

import requests
import six

import plynx.utils.executor
from plynx.base.executor import BaseExecutor
from plynx.constants import NodeRunningStatus
from plynx.db.worker_state import WorkerState
from plynx.utils.common import JSONEncoder, ObjectId
from plynx.utils.config import WorkerConfig, get_web_config, get_worker_config
from plynx.utils.file_handler import upload_file_stream

CONNECT_POST_TIMEOUT = 1.0
NUM_RETRIES = 3
REQUESTS_TIMEOUT = 10


def urljoin(base: str, postfix: str) -> str:
    """Join urls in a reasonable way"""
    if base[-1] == "/":
        return f"{base}{postfix}"
    return f"{base}/{postfix}"


def post_request(uri, data, num_retries=NUM_RETRIES):
    """Make post request to the url"""
    url = urljoin(get_web_config().internal_endpoint, uri)
    json_data = JSONEncoder().encode(data)
    for iter_num in range(num_retries):
        if iter_num != 0:
            time.sleep(CONNECT_POST_TIMEOUT)
        response = requests.post(url=url, data=json_data, timeout=REQUESTS_TIMEOUT)
        if response.ok:
            return json.loads(response.text)
    return None


class TickThread:
    """
    This class is a Context Manager wrapper.
    It calls method `tick()` of the executor with a given interval
    """

    TICK_TIMEOUT: int = 1

    def __init__(self, executor: BaseExecutor):
        self.executor = executor
        self._stop_event = threading.Event()
        self._tick_thread = threading.Thread(target=self.call_executor_tick, args=())

    def __enter__(self):
        """
        Currently no meaning of returned class
        """
        self._tick_thread.start()
        return self

    def __exit__(self, type_cls, value, traceback_val):
        self._stop_event.set()

    def call_executor_tick(self):
        """Run timed ticks"""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=TickThread.TICK_TIMEOUT)
            if self.executor.is_updated():
                # Save logs when operation is running
                if NodeRunningStatus.is_finished(self.executor.node.node_running_status):
                    break
                resp = post_request("update_run", data={"node": self.executor.node.to_dict()})
                logging.info(f"TickThread:Run update res: {resp}")


class DBJobExecutor:
    """Executes a single job in an executor and updates its status."""

    def __init__(self, executor: BaseExecutor):
        assert executor.node, "Executor has no `node` attribute defined"
        self.executor = executor
        self._killed = False

    def run(self) -> str:
        """Run the job in the executor"""
        assert self.executor.node, "Executor has no `node` attribute defined"
        try:
            try:
                status = NodeRunningStatus.FAILED
                self.executor.init_executor()
                with TickThread(self.executor):
                    status = self.executor.run()
            except Exception:   # pylint: disable=broad-except
                try:
                    f = six.BytesIO()
                    f.write(traceback.format_exc().encode())
                    self.executor.node.get_log_by_name('worker').resource_id = upload_file_stream(f)
                    logging.error(traceback.format_exc())
                except Exception:   # pylint: disable=broad-except
                    # This case of `except` has happened before due to I/O failure
                    logging.critical(traceback.format_exc())
                    raise
            finally:
                self.executor.clean_up_executor()

            logging.info(f"Node {self.executor.node._id} `{self.executor.node.title}` finished with status `{status}`")
            self.executor.node.node_running_status = status
        except Exception as e:  # pylint: disable=broad-except
            logging.warning(f"Execution failed: {e}")
            self.executor.node.node_running_status = NodeRunningStatus.FAILED
        finally:
            resp = post_request("update_run", data={"node": self.executor.node.to_dict()}, num_retries=3)
            logging.info(f"Worker:Run update res: {resp}")

            self._killed = True

        return status

    def kill(self) -> None:
        """Kill the running job"""
        assert self.executor.node, "Executor has no `node` attribute defined"
        if self._killed:
            return
        if NodeRunningStatus.is_finished(self.executor.node.node_running_status):
            self.executor.kill()
        self._killed = True


class Worker:
    # TODO update docstring
    """Worker main class.

    On the high level Worker distributes Jobs over all available Workers
    and updates statuses of the Graphs in the database.

    Worker performs several roles:
        * Pull graphs in status READY from the database.
        * Create Schedulers for each Graph.
        * Populate the queue of the Jobs.
        * Distribute Jobs accross Workers.
        * Keep track of Job's statuses.
        * Process CANCEL requests.
        * Update Graph's statuses.
        * Track worker status and last response.
    """
    # pylint: disable=too-many-instance-attributes

    # Define sync with database timeout
    SDB_STATUS_UPDATE_TIMEOUT: int = 1

    # Worker State update timeout
    WORKER_STATE_UPDATE_TIMEOUT: int = 1

    def __init__(self, worker_config: WorkerConfig, worker_id: Optional[str]):
        self.worker_id = worker_id if worker_id else str(uuid.uuid1())
        self.kinds = worker_config.kinds
        self.host = socket.gethostname()
        self._stop_event = threading.Event()

        # Mapping keep track of Worker Status
        self._run_id_to_executor: Dict[ObjectId, BaseExecutor] = {}
        self._run_id_to_executor_lock = threading.Lock()

        # Start new threads
        self._thread_db_status_update = threading.Thread(target=self._run_db_status_update, args=())
        self._thread_db_status_update.start()

        self._thread_worker_state_update = threading.Thread(target=self._run_worker_state_update, args=())
        self._thread_worker_state_update.start()

        self._killed_run_ids: Set[ObjectId] = set()

    def serve_forever(self):
        """
        Run the worker.
        """
        self._stop_event.wait()

    def execute_job(self, executor: BaseExecutor):
        """Run a single job in the executor"""
        assert executor.node, "Executor has no `node` attribute defined"
        db_executor = DBJobExecutor(executor)
        db_executor.run()

        with self._run_id_to_executor_lock:
            del self._run_id_to_executor[executor.node._id]

    def _run_db_status_update(self):
        """Syncing with the database."""
        try:
            while not self._stop_event.is_set():
                response = post_request("pick_run", data={"kinds": self.kinds})
                if response:
                    node = response["node"]
                else:
                    node = None
                    logging.error("Failed to pick a run.")

                if node:
                    logging.info(f"New node found: {node['_id']} {node['node_running_status']} {node['title']}")
                    executor = plynx.utils.executor.materialize_executor(node)

                    with self._run_id_to_executor_lock:
                        self._run_id_to_executor[executor.node._id] = executor
                    thread = threading.Thread(target=self.execute_job, args=(executor, ))
                    thread.start()

                else:
                    self._stop_event.wait(timeout=Worker.SDB_STATUS_UPDATE_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info(f"Exit {self._run_db_status_update.__name__}")

    def _run_worker_state_update(self):
        """Syncing with the database."""
        try:
            while not self._stop_event.is_set():
                # TODO move CANCEL to a separate thread
                run_ids = list(self._run_id_to_executor.keys())
                if run_ids:
                    response = post_request("get_run_cancelations", data={"run_ids": run_ids}, num_retries=1)
                    runs_to_kill = [] if not response else response["run_ids_to_cancel"]
                    for run_id in runs_to_kill:
                        self._run_id_to_executor[run_id].kill()

                runs = []
                with self._run_id_to_executor_lock:
                    for executor in self._run_id_to_executor.values():
                        runs.append(executor.node.to_dict())
                worker_state = WorkerState(
                    worker_id=self.worker_id,
                    host=self.host,
                    runs=runs,
                    kinds=self.kinds,
                )
                post_request("push_worker_state", data={"worker_state": worker_state.to_dict()}, num_retries=1)
                self._stop_event.wait(timeout=Worker.WORKER_STATE_UPDATE_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info(f"Exit {self._run_worker_state_update.__name__}")

    def stop(self):
        """Stop worker."""
        self._stop_event.set()


def run_worker(worker_id: Optional[str] = None):
    """Run worker daemon. It will run in the same thread."""
    logging.info('Init Worker')
    worker_config = get_worker_config()
    logging.info(worker_config)
    worker = Worker(worker_config, worker_id)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        logging.info("Start serving")
        worker.serve_forever()
    except KeyboardInterrupt:
        worker.stop()
        sys.exit(0)
