import os
import sys
import threading
import logging
import queue
import time
import six
import traceback
import uuid
from collections import namedtuple
from plynx.constants import JobReturnStatus, NodeRunningStatus, GraphRunningStatus
from plynx.db.node_collection_manager import NodeCollectionManager
from plynx.db.service_state import MasterState, WorkerState
from plynx.utils.config import get_master_config
from plynx.graph.base_nodes import NodeCollection
from plynx.utils.db_connector import check_connection
from plynx.plugins.executors import materialize_executor
from plynx.utils.file_handler import upload_file_stream


MasterJobDescription = namedtuple('MasterJobDescription', ['graph_id', 'job'])

node_collection_manager = NodeCollectionManager(collection='runs')
# graph_cancellation_manager = GraphCancellationManager()
node_collection = NodeCollection()


class Master(object):
    """Master main class.

    Args:
        server_address      (tuple):        Define the server address (host, port).
        RequestHandlerClass (TCP handler):  Class of socketserver.BaseRequestHandler.

    Currently implemented as a TCP server.

    Only a single instance of the Master class in a cluster is allowed.

    On the high level Master distributes Jobs over all available Workers
    and updates statuses of the Graphs in the database.

    Master performs several roles:
        * Pull graphs in status READY from the database.
        * Create Schedulers for each Graph.
        * Populate the queue of the Jobs.
        * Distribute Jobs accross Workers.
        * Keep track of Job's statuses.
        * Process CANCEL requests.
        * Update Graph's statuses.
        * Track worker status and last response.
    """

    # Ctrl-C will cleanly kill all spawned threads
    daemon_threads = True
    # much faster rebinding
    allow_reuse_address = True
    # Define timeout for scheduler iteration
    SCHEDULER_TIMEOUT = 1
    # Define sync with database timeout
    SDB_STATUS_UPDATE_TIMEOUT = 1
    # Threshold to tolerate delays before declaring worker failed
    MAX_HEARTBEAT_DELAY = 10
    # Recalculating Workers' statuses timeout
    WORKER_MONITORING_TIMEOUT = 10

    def __init__(self, master_config):
        self.executors = master_config.executors
        self._stop_event = threading.Event()
        self._job_description_queue = queue.Queue()
        # Mapping of Worker ID to WorkerInfo
        self._worker_to_info = {}
        self._worker_to_info_lock = threading.Lock()

        self._graph_id_to_scheduler = {}
        self._new_graph_schedulers = []
        self._graph_schedulers_lock = threading.Lock()

        # Start new threads
        self._thread_db_status_update = threading.Thread(target=self._run_db_status_update, args=())
        self._thread_db_status_update.start()

        """
        self._thread_worker_monitoring = threading.Thread(target=self._run_worker_monitoring, args=())
        self._thread_worker_monitoring.daemon = True    # Daemonize thread
        self._thread_worker_monitoring.start()
        """

    def serve_forever(self):
        """
        Run the master.
        """
        self._stop_event.wait()

    def execute_job(self, executor):
        try:
            timeout_parameter = executor.node.get_parameter_by_name('_timeout', throw=False)
            if timeout_parameter:
                _node_timeout = int(timeout_parameter.value)
            else:
                _node_timeout = None

            try:
                status = JobReturnStatus.FAILED
                if not executor.workdir:
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
        except Exception:
            executor.node.node_running_status = NodeRunningStatus.FAILED
        finally:
            executor.node.save(collection='runs')

    def _run_db_status_update(self):
        """Syncing with the database."""
        try:
            while not self._stop_event.is_set():
                node = node_collection_manager.pick_node(kinds=self.executors)
                if node:
                    logging.info('New node found: {} {} {}'.format(node['_id'], node['node_running_status'], node['title']))
                    executor = materialize_executor(node)

                    thread = threading.Thread(target=self.execute_job, args=(executor, ))
                    thread.start()

                else:
                    self._stop_event.wait(timeout=Master.SDB_STATUS_UPDATE_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info("Exit {}".format(self._run_db_status_update.__name__))

    def _run_worker_monitoring(self):
        try:
            while not self._stop_event.is_set():
                current_time = time.time()
                with self._worker_to_info_lock:
                    dead_worker_ids = [
                        worker_id
                        for worker_id, worker_info in self._worker_to_info.items()
                        if worker_info.last_heartbeat_ts and current_time - worker_info.last_heartbeat_ts > Master.MAX_HEARTBEAT_DELAY
                    ]
                for worker_id in dead_worker_ids:
                    logging.info("Found dead Worker: worker_id=`{}`".format(worker_id))
                    job_description = self.get_job_description(worker_id)
                    self._del_worker_info(worker_id)
                    if not job_description:
                        continue
                    with self._graph_schedulers_lock:
                        scheduler = self._graph_id_to_scheduler.get(job_description.graph_id, None)
                        if scheduler:
                            node = job_description.job.node
                            node.node_running_status = NodeRunningStatus.FAILED
                            scheduler.update_node(node)

                # Update master state
                master_state = MasterState()
                with self._worker_to_info_lock:
                    for worker_id, worker_info in self._worker_to_info.items():
                        if worker_info.job_description:
                            graph_id = worker_info.job_description.graph_id
                            node = worker_info.job_description.job.node.to_dict()
                        else:
                            graph_id, node = None, None
                        worker_state = WorkerState({
                            'worker_id': worker_id,
                            'graph_id': graph_id,
                            'node': node,
                            'host': worker_info.host,
                            'num_finished_jobs': worker_info.num_finished_jobs,
                        })
                        master_state.workers.append(worker_state)

                        worker_info.num_finished_jobs = 0

                master_state.save()

                self._stop_event.wait(timeout=Master.WORKER_MONITORING_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info("Exit {}".format(self._run_worker_monitoring.__name__))

    def _del_worker_info(self, worker_id):
        with self._worker_to_info_lock:
            if worker_id in self._worker_to_info:
                del self._worker_to_info[worker_id]

    def _del_job_description(self, worker_id):
        with self._worker_to_info_lock:
            worker_info = self._worker_to_info.get(worker_id, None)
            if worker_info:
                self._worker_to_info[worker_id].job_description = None
                worker_info.num_finished_jobs += 1
                return True
            return False

    def _get_job_description_from_queue(self):
        try:
            job_description = self._job_description_queue.get_nowait()
            self._job_description_queue.task_done()
            return job_description
        except queue.Empty:
            return None

    def get_job_description(self, worker_id):
        with self._worker_to_info_lock:
            worker_info = self._worker_to_info.get(worker_id, None)
            if worker_info:
                return worker_info.job_description
            return None

    def update_node(self, worker_id, node):
        """Return True Job is in the queue, else False."""
        job_description = self.get_job_description(worker_id)
        if job_description:
            with self._graph_schedulers_lock:
                scheduler = self._graph_id_to_scheduler.get(job_description.graph_id, None)
                if scheduler:
                    scheduler.update_node(node)
            if NodeRunningStatus.is_finished(node.node_running_status):
                self._del_job_description(worker_id)

            # If scheduler was not found, it means the graph was canceled, failed, finished, etc.
            # if scheduler is None, the graph can't be updated.
            return scheduler is not None
        else:
            logging.info("Scheduler was not found for worker `{}`".format(worker_id))
        return False

    def track_worker(self, worker_id, host):
        """Track worker existance and responsiveness."""
        with self._worker_to_info_lock:
            worker_info = self._worker_to_info.get(worker_id, None)
            if worker_info:
                worker_info.last_heartbeat_ts = time.time()
                worker_info.host = host

    def stop(self):
        """Stop Master."""
        self._stop_event.set()


def run_master():
    """Run master Daemon. It will run in the same thread."""
    # Check connection to the db
    check_connection()

    logging.info('Init Master')
    master_config = get_master_config()
    logging.info(master_config)
    master = Master(master_config)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        logging.info("Start serving")
        master.serve_forever()
    except KeyboardInterrupt:
        master.stop()
        sys.exit(0)
