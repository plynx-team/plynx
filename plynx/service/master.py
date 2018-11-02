import argparse
import socket
import sys
import SocketServer
import pickle
import threading
import logging
from collections import deque, namedtuple
from time import sleep
from . import WorkerMessage, RunStatus, WorkerMessageType, MasterMessageType, MasterMessage, send_msg, recv_msg
from plynx.constants import NodeRunningStatus, GraphRunningStatus
from plynx.db import GraphCollectionManager
from plynx.db import GraphCancelationManager
from plynx.graph.graph_scheduler import GraphScheduler
from plynx.utils.config import get_master_config
from plynx.utils.logs import set_logging_level
from plynx.graph.base_nodes import NodeCollection


MasterJobDescription = namedtuple('MasterJobDescription', ['graph_id', 'job'])

graph_collection_manager = GraphCollectionManager()
graph_cancelation_manager = GraphCancelationManager()
# TODO node_collection needed?
node_collection = NodeCollection()


class ClientTCPHandler(SocketServer.BaseRequestHandler):
    """
    The request handler class for our server.

    It is instantiated once per connection to the server, and must
    override the handle() method to implement communication to the
    client.
    """

    def handle(self):
        # self.request is the TCP socket connected to the client
        worker_message = recv_msg(self.request)
        worker_id = worker_message.worker_id
        graph_id = worker_message.graph_id
        response = None
        if worker_message.message_type == WorkerMessageType.HEARTBEAT:
            if worker_message.run_status == RunStatus.IDLE:
                self.server.allocate_job(worker_message.worker_id)
            elif worker_message.run_status == RunStatus.RUNNING:
                node = worker_message.body.node
                node.node_running_status = NodeRunningStatus.RUNNING
                if not self.server.update_node(worker_id, node):
                    # Kill the job if it is not found in the scheduler
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


class Master(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    """
    Master main class: TCP server.
    """

    # Ctrl-C will cleanly kill all spawned threads
    daemon_threads = True
    # much faster rebinding
    allow_reuse_address = True
    # Define timeout for scheduler iteration
    SCHEDULER_TIMEOUT = 1
    # Define sync with database timeout
    SDB_STATUS_UPDATE_TIMEOUT = 1

    def __init__(self, server_address, RequestHandlerClass):
        """
        Args:
            server_address: tuple (host, port)
            RequestHandlerClass: TCP handler. Class of SocketServer.BaseRequestHandler
        """
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        self._alive = True
        self._job_description_queue = deque()
        self._job_description_queue_lock = threading.Lock()
        # Mapping of Worker ID to the job description
        self._worker_to_job_description = {}

        # Pick up all the graphs with status RUNNING and set it to READY
        # The have probably been in progress then the their master exited
        running_graphs = graph_collection_manager.get_graphs(GraphRunningStatus.RUNNING)
        if len(running_graphs) > 0:
            logging.info("Found {} running graphs. Setting them to 'READY'".format(len(running_graphs)))
            for graph in running_graphs:
                graph.graph_running_status = GraphRunningStatus.READY
                for node in graph.nodes:
                    if node.node_running_status in [NodeRunningStatus.RUNNING, NodeRunningStatus.IN_QUEUE]:
                        node.node_running_status = NodeRunningStatus.CREATED
                graph.save()

        self._graph_id_to_scheduler = {}
        self._new_graph_schedulers = []
        self._new_graph_schedulers_lock = threading.Lock()

        # Start new threads
        self._thread_db_status_update = threading.Thread(target=self._run_db_status_update, args=())
        self._thread_db_status_update.daemon = True     # Daemonize thread
        self._thread_db_status_update.start()

        self._thread_scheduler = threading.Thread(target=self._run_scheduler, args=())
        self._thread_scheduler.daemon = True            # Daemonize thread
        self._thread_scheduler.start()

    def _run_db_status_update(self):
        """
        Syncing with the database
        """
        while self._alive:
            graphs = graph_collection_manager.get_graphs(GraphRunningStatus.READY)
            for graph in graphs:
                graph_scheduler = GraphScheduler(graph, node_collection)
                graph_scheduler.graph.graph_running_status = GraphRunningStatus.RUNNING
                graph_scheduler.graph.save()

                with self._new_graph_schedulers_lock:
                    self._new_graph_schedulers.append(graph_scheduler)

            sleep(Master.SDB_STATUS_UPDATE_TIMEOUT)

    def _run_scheduler(self):
        """
        Synchronization of the Schedules.
        The process picks up new graphs from _run_db_status_update(). Also it queries each scheduler for new jobs and puts them into the queue.
        """
        while self._alive:
            # add new schedules
            with self._new_graph_schedulers_lock:
                self._graph_id_to_scheduler.update(
                    {
                        graph_scheduler.graph._id: graph_scheduler for graph_scheduler in self._new_graph_schedulers
                    })
                self._new_graph_schedulers = []

            # TODO Posibly Race Condition with the DB
            # Some nodes might be updated to "PROCESSING" when shoud stay CANCELED
            graph_cancelations = list(graph_cancelation_manager.get_new_graph_cancelations())
            for graph_cancelation in graph_cancelations:
                if graph_cancelation.graph_id in self._graph_id_to_scheduler:
                    # TODO: check race condition
                    self._graph_id_to_scheduler[graph_cancelation.graph_id].graph.cancel()
            graph_cancelation_manager.remove([graph_cancelation._id for graph_cancelation in graph_cancelations])

            new_to_queue = []
            finished_graph_ids = []
            for graph_id, scheduler in self._graph_id_to_scheduler.iteritems():
                if scheduler.finished():
                    finished_graph_ids.append(graph_id)
                    continue
                new_to_queue.extend([
                    MasterJobDescription(graph_id=graph_id, job=job) for job in scheduler.pop_jobs()
                ])

            for graph_id in finished_graph_ids:
                del self._graph_id_to_scheduler[graph_id]

            with self._job_description_queue_lock:
                self._job_description_queue.extend(new_to_queue)
                if new_to_queue:
                    logging.info('Queue length: {}'.format(len(self._job_description_queue)))

            sleep(Master.SCHEDULER_TIMEOUT)

    def _del_job_description(self, worker_id):
        with self._job_description_queue_lock:
            if worker_id in self._worker_to_job_description:
                del self._worker_to_job_description[worker_id]
                return True
            return False

    def allocate_job(self, worker_id):
        with self._job_description_queue_lock:
            if len(self._job_description_queue) == 0:                   # No jobs to allocate
                return False
            if worker_id in self._worker_to_job_description:            # worker already has a job
                return False
            while self._job_description_queue:
                job_description = self._job_description_queue.popleft()
                scheduler = self._graph_id_to_scheduler.get(job_description.graph_id, None)
                # CANCELED and FAILED Graphs should not have jobs assigned
                if scheduler and scheduler.graph.graph_running_status == GraphRunningStatus.RUNNING:
                    self._worker_to_job_description[worker_id] = job_description
                    node = job_description.job.node
                    node.node_running_status = NodeRunningStatus.IN_QUEUE
                    scheduler.update_node(node)
                    logging.info('Queue length: {}'.format(len(self._job_description_queue)))
                    return True
        return False

    def get_job_description(self, worker_id):
        with self._job_description_queue_lock:
            return self._worker_to_job_description.get(worker_id, None)

    def update_node(self, worker_id, node):
        """Return True Job is in the queue, else False"""
        job_description = self.get_job_description(worker_id)
        if job_description:
            with self._new_graph_schedulers_lock:
                scheduler = self._graph_id_to_scheduler.get(job_description.graph_id, None)
                if scheduler:
                    scheduler.update_node(node)
            if NodeRunningStatus.is_finished(node.node_running_status):
                self._del_job_description(worker_id)
            return True
        else:
            logging.info("Scheduler was not found for worker `{}`".format(worker_id))
        return False



def parse_arguments():
    parser = argparse.ArgumentParser(description='Master launcher')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    set_logging_level(args.verbose)
    logging.info("Init master")

    master_config = get_master_config()
    server = Master((master_config.host, master_config.port), ClientTCPHandler)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        logging.info("Start serving")
        server.serve_forever()
    except KeyboardInterrupt:
        server._alive = False
        sys.exit(0)
