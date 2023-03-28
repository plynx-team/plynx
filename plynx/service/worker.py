"""Main PLynx worker service and utils"""

import logging
import socket
import sys
import threading
import uuid
from typing import Dict, Optional, Set

from plynx.base.executor import BaseExecutor
from plynx.db.worker_state import WorkerState
from plynx.utils.common import ObjectId
from plynx.utils.config import WorkerConfig, get_worker_config
from plynx.utils.executor import DBJobExecutor, materialize_executor, post_request


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
                    executor = materialize_executor(node)

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
