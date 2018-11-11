import sys
import socketserver
import threading
import logging
import queue
import time
from collections import namedtuple
from plynx.service import (
    RunStatus,
    WorkerMessageType,
    MasterMessageType,
    MasterMessage,
    send_msg,
    recv_msg,
)
from plynx.constants import NodeRunningStatus, GraphRunningStatus
from plynx.db import GraphCollectionManager, GraphCancellationManager
from plynx.graph.graph_scheduler import GraphScheduler
from plynx.utils.config import get_master_config
from plynx.graph.base_nodes import NodeCollection


MasterJobDescription = namedtuple('MasterJobDescription', ['graph_id', 'job'])

graph_collection_manager = GraphCollectionManager()
graph_cancellation_manager = GraphCancellationManager()
node_collection = NodeCollection()


class ClientTCPHandler(socketserver.BaseRequestHandler):
    """The request handler class for Master server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        """Handle TCP connection."""
        worker_message = recv_msg(self.request)
        worker_id = worker_message.worker_id
        graph_id = worker_message.graph_id
        response = None
        if worker_message.message_type == WorkerMessageType.HEARTBEAT:
            # track worker existance and responsiveness
            self.server.track_worker(worker_message.worker_id)

            # check worker status
            if worker_message.run_status == RunStatus.IDLE:
                self.server.allocate_job(worker_message.worker_id)
            elif worker_message.run_status == RunStatus.RUNNING:
                node = worker_message.body.node
                node.node_running_status = NodeRunningStatus.RUNNING
                if not self.server.update_node(worker_id, node):
                    # Kill the Job if it is not found in the Scheduler
                    response = MasterMessage(
                        worker_id=worker_id,
                        message_type=MasterMessageType.KILL,
                        job=node._id,
                        graph_id=graph_id
                    )

            if not response:
                response = self.make_aknowledge_message(worker_id)

        elif worker_message.message_type == WorkerMessageType.GET_JOB:
            job_description = self.server.get_job_description(worker_id)
            if job_description:
                response = MasterMessage(
                    worker_id=worker_id,
                    message_type=MasterMessageType.SET_JOB,
                    job=job_description.job,
                    graph_id=job_description.graph_id
                )
                logging.info("SET_JOB worker_id: {}".format(worker_id))
            else:
                response = self.make_aknowledge_message(worker_id)

        elif worker_message.message_type == WorkerMessageType.JOB_FINISHED_SUCCESS:
            node = worker_message.body.node
            node.node_running_status = NodeRunningStatus.SUCCESS
            if self.server.update_node(worker_id, node):
                logging.info("Job `{}` marked as SUCCESSFUL".format(node._id))
            else:
                logging.info(
                    "Scheduler not found for Job `{}`. Graph `{}` might have been be canceled".format(node._id, graph_id)
                )

            response = self.make_aknowledge_message(worker_id)

        elif worker_message.message_type == WorkerMessageType.JOB_FINISHED_FAILED:
            node = worker_message.body.node
            node.node_running_status = NodeRunningStatus.FAILED
            if self.server.update_node(worker_id, node):
                logging.info("Job `{}` marked as FAILED".format(node._id))
            else:
                logging.info(
                    "Scheduler not found for Job `{}`. Graph `{}` might have been be canceled".format(node._id, graph_id)
                )

            response = self.make_aknowledge_message(worker_id)

        if response:
            send_msg(self.request, response)

    @staticmethod
    def make_aknowledge_message(worker_id):
        return MasterMessage(
            worker_id=worker_id,
            message_type=MasterMessageType.AKNOWLEDGE,
            job=None,
            graph_id=None
        )


class Master(socketserver.ThreadingMixIn, socketserver.TCPServer):
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

    def __init__(self, server_address, RequestHandlerClass):
        socketserver.TCPServer.__init__(self, server_address, RequestHandlerClass)
        self._stop_event = threading.Event()
        self._job_description_queue = queue.Queue()
        # Mapping of Worker ID to the Job Description
        self._worker_to_job_description = {}
        self._worker_to_last_heartbeat = {}
        self._worker_to_job_description_lock = threading.Lock()

        # Pick up all the Graphs with status RUNNING and set it to READY
        # The have probably been in progress then the their master exited
        running_graphs = graph_collection_manager.get_graphs(GraphRunningStatus.RUNNING)
        if len(running_graphs) > 0:
            logging.info(
                "Found {} running graphs. Setting them to '{}' state".format(
                    len(running_graphs),
                    GraphRunningStatus.READY,
                )
            )
            for graph in running_graphs:
                graph.graph_running_status = GraphRunningStatus.READY
                for node in graph.nodes:
                    if node.node_running_status in [NodeRunningStatus.RUNNING, NodeRunningStatus.IN_QUEUE]:
                        node.node_running_status = NodeRunningStatus.CREATED
                graph.save()

        self._graph_id_to_scheduler = {}
        self._new_graph_schedulers = []
        self._graph_schedulers_lock = threading.Lock()

        # Start new threads
        self._thread_db_status_update = threading.Thread(target=self._run_db_status_update, args=())
        self._thread_db_status_update.daemon = True     # Daemonize thread
        self._thread_db_status_update.start()

        self._thread_scheduler = threading.Thread(target=self._run_scheduler, args=())
        self._thread_scheduler.daemon = True            # Daemonize thread
        self._thread_scheduler.start()

        self._thread_worker_monitoring = threading.Thread(target=self._run_worker_monitoring, args=())
        self._thread_worker_monitoring.daemon = True    # Daemonize thread
        self._thread_worker_monitoring.start()

    def _run_db_status_update(self):
        """Syncing with the database."""
        try:
            while not self._stop_event.is_set():
                graphs = graph_collection_manager.get_graphs(GraphRunningStatus.READY)
                for graph in graphs:
                    graph_scheduler = GraphScheduler(graph, node_collection)
                    graph_scheduler.graph.graph_running_status = GraphRunningStatus.RUNNING
                    graph_scheduler.graph.save()

                    with self._graph_schedulers_lock:
                        self._new_graph_schedulers.append(graph_scheduler)

                self._stop_event.wait(timeout=Master.SDB_STATUS_UPDATE_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info("Exit {}".format(self._run_db_status_update.__name__))

    def _run_scheduler(self):
        """
        Synchronization of the Schedules.
        The process picks up new Graphs from _run_db_status_update().
        It also queries each Scheduler for the new Jobs and puts them into the queue.
        """
        try:
            while not self._stop_event.is_set():
                with self._graph_schedulers_lock:
                    # add new Schedules
                    self._graph_id_to_scheduler.update(
                        {
                            graph_scheduler.graph._id: graph_scheduler
                            for graph_scheduler in self._new_graph_schedulers
                        })
                    self._new_graph_schedulers = []

                    # pull Graph cancellation events and cancel the Graphs
                    graph_cancellations = list(graph_cancellation_manager.get_graph_cancellations())
                    for graph_cancellation in graph_cancellations:
                        if graph_cancellation.graph_id in self._graph_id_to_scheduler:
                            self._graph_id_to_scheduler[graph_cancellation.graph_id].graph.cancel()
                    graph_cancellation_manager.remove([graph_cancellation._id for graph_cancellation in graph_cancellations])

                    # check the running Schedulers
                    new_to_queue = []
                    finished_graph_ids = []
                    for graph_id, scheduler in self._graph_id_to_scheduler.items():
                        if scheduler.finished():
                            finished_graph_ids.append(graph_id)
                            continue
                        # pop new Jobs
                        new_to_queue.extend([
                            MasterJobDescription(graph_id=graph_id, job=job) for job in scheduler.pop_jobs()
                        ])

                    # remove Schedulers with finished Graphs
                    for graph_id in finished_graph_ids:
                        del self._graph_id_to_scheduler[graph_id]

                # End self._graph_schedulers_lock

                for job_description in new_to_queue:
                    self._job_description_queue.put(job_description)
                if new_to_queue:
                    logging.info('Queue length: {}'.format(self._job_description_queue.qsize()))

                self._stop_event.wait(timeout=Master.SCHEDULER_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info("Exit {}".format(self._run_scheduler.__name__))

    def _run_worker_monitoring(self):
        try:
            while not self._stop_event.is_set():
                current_time = time.time()
                with self._worker_to_job_description_lock:
                    dead_worker_ids = [
                        worker_id
                        for worker_id, last_time in self._worker_to_last_heartbeat.items()
                        if current_time - last_time > Master.MAX_HEARTBEAT_DELAY
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

                self._stop_event.wait(timeout=Master.WORKER_MONITORING_TIMEOUT)
        except Exception:
            self.stop()
            raise
        finally:
            logging.info("Exit {}".format(self._run_worker_monitoring.__name__))

    def _del_worker_info(self, worker_id):
        with self._worker_to_job_description_lock:
            if worker_id in self._worker_to_job_description:
                del self._worker_to_job_description[worker_id]
            if worker_id in self._worker_to_last_heartbeat:
                del self._worker_to_last_heartbeat[worker_id]

    def _del_job_description(self, worker_id):
        with self._worker_to_job_description_lock:
            if worker_id in self._worker_to_job_description:
                del self._worker_to_job_description[worker_id]
                return True
            return False

    def _get_job_description_from_queue(self):
        try:
            job_description = self._job_description_queue.get_nowait()
            self._job_description_queue.task_done()
            return job_description
        except queue.Empty:
            return None

    def allocate_job(self, worker_id):
        with self._worker_to_job_description_lock:
            if worker_id in self._worker_to_job_description:            # worker already has a Job
                return False
        while True:
            job_description = self._get_job_description_from_queue()
            if not job_description:
                return False
            with self._graph_schedulers_lock:
                scheduler = self._graph_id_to_scheduler.get(job_description.graph_id, None)
                # CANCELED and FAILED Graphs should not have jobs assigned. Check for RUNNING status
                if scheduler and scheduler.graph.graph_running_status == GraphRunningStatus.RUNNING:
                    with self._worker_to_job_description_lock:
                        self._worker_to_job_description[worker_id] = job_description
                    node = job_description.job.node
                    node.node_running_status = NodeRunningStatus.IN_QUEUE
                    scheduler.update_node(node)
                    logging.info('Queue length: {}'.format(self._job_description_queue.qsize()))
                    return True
        return False

    def get_job_description(self, worker_id):
        with self._worker_to_job_description_lock:
            return self._worker_to_job_description.get(worker_id, None)

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
            return True
        else:
            logging.info("Scheduler was not found for worker `{}`".format(worker_id))
        return False

    def track_worker(self, worker_id):
        """Track worker existance and responsiveness."""
        with self._worker_to_job_description_lock:
            self._worker_to_last_heartbeat[worker_id] = time.time()

    def stop(self):
        """Stop Master."""
        self._stop_event.set()
        self.shutdown()


def run_master():
    """Run master Daemon. It will run in the same thread."""
    logging.info('Init Master')
    master_config = get_master_config()
    logging.info(master_config)
    master = Master((master_config.host, master_config.port), ClientTCPHandler)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        logging.info("Start serving")
        master.serve_forever()
    except KeyboardInterrupt:
        master.stop()
        sys.exit(0)
