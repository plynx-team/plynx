import os
import sys
import threading
import logging
import six
import traceback
import uuid
import socket
from plynx.constants import JobReturnStatus, NodeRunningStatus, Collections
from plynx.db.node_collection_manager import NodeCollectionManager
from plynx.db.worker_state import WorkerState
from plynx.utils.config import get_worker_config
from plynx.utils.db_connector import check_connection
import plynx.utils.executor
from plynx.utils.file_handler import upload_file_stream


class Worker(object):
    """Worker main class.

    Args:
        server_address      (tuple):        Define the server address (host, port).
        RequestHandlerClass (TCP handler):  Class of socketserver.BaseRequestHandler.

    Currently implemented as a TCP server.

    Only a single instance of the Worker class in a cluster is allowed.

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

    # Define sync with database timeout
    SDB_STATUS_UPDATE_TIMEOUT = 1

    # Worker State update timeout
    WORKER_STATE_UPDATE_TIMEOUT = 1

    def __init__(self, worker_config, worker_id):
        self.worker_id = worker_id if worker_id else str(uuid.uuid1())
        self.node_collection_manager = NodeCollectionManager(collection=Collections.RUNS)
        self.kinds = worker_config.kinds
        self.host = socket.gethostname()
        self._stop_event = threading.Event()

        # Mapping keep track of Worker Status
        self._run_id_to_run = {}
        self._run_id_to_run_lock = threading.Lock()

        # Start new threads
        self._thread_db_status_update = threading.Thread(target=self._run_db_status_update, args=())
        self._thread_db_status_update.start()

        self._thread_worker_state_update = threading.Thread(target=self._run_worker_state_update, args=())
        self._thread_worker_state_update.start()

    def serve_forever(self):
        """
        Run the worker.
        """
        self._stop_event.wait()

    def execute_job(self, executor):
        try:
            try:
                status = JobReturnStatus.FAILED
                executor.workdir = os.path.join('/tmp', str(uuid.uuid1()))
                executor.init_workdir()
                status = executor.run()
            except Exception:
                try:
                    f = six.BytesIO()
                    f.write(traceback.format_exc().encode())
                    executor.node.get_log_by_name('worker').resource_id = upload_file_stream(f)
                    logging.error(traceback.format_exc())
                except Exception:
                    logging.critical(traceback.format_exc())
                    raise
            finally:
                executor.clean_up()

            self._job_killed = True
            logging.info('Node {node_id} `{title}` finished with status `{status}`'.format(
                node_id=executor.node._id,
                title=executor.node.title,
                status=status,
                ))
            if status == JobReturnStatus.SUCCESS:
                executor.node.node_running_status = NodeRunningStatus.SUCCESS
            elif status == JobReturnStatus.FAILED:
                executor.node.node_running_status = NodeRunningStatus.FAILED
            else:
                raise Exception("Unknown return status value: `{}`".format(status))
        except Exception as e:
            logging.warning('Execution failed: {}'.format(e))
            executor.node.node_running_status = NodeRunningStatus.FAILED
        finally:
            executor.node.save(collection='runs')
            with self._run_id_to_run_lock:
                del self._run_id_to_run[executor.node._id]

    def _run_db_status_update(self):
        """Syncing with the database."""
        try:
            while not self._stop_event.is_set():
                node = self.node_collection_manager.pick_node(kinds=self.kinds)
                if node:
                    logging.info('New node found: {} {} {}'.format(node['_id'], node['node_running_status'], node['title']))
                    executor = plynx.utils.executor.materialize_executor(node)

                    with self._run_id_to_run_lock:
                        self._run_id_to_run[executor.node._id] = node
                    thread = threading.Thread(target=self.execute_job, args=(executor, ))
                    thread.start()

                else:
                    self._stop_event.wait(timeout=Worker.SDB_STATUS_UPDATE_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info("Exit {}".format(self._run_db_status_update.__name__))

    def _run_worker_state_update(self):
        """Syncing with the database."""
        try:
            while not self._stop_event.is_set():
                with self._run_id_to_run_lock:
                    runs = list(self._run_id_to_run.values())
                worker_state = WorkerState.from_dict({
                    'worker_id': self.worker_id,
                    'host': self.host,
                    'runs': runs,
                    'kinds': self.kinds,
                })
                worker_state.save()
                self._stop_event.wait(timeout=Worker.WORKER_STATE_UPDATE_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info("Exit {}".format(self._run_worker_state_update.__name__))

    def stop(self):
        """Stop worker."""
        self._stop_event.set()


def run_worker(worker_id=None):
    """Run worker daemon. It will run in the same thread."""
    # Check connection to the db
    check_connection()

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
