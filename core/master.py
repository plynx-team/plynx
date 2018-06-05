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
from constants import NodeRunningStatus, GraphRunningStatus
from db import GraphCollectionManager
from graph.graph_scheduler import GraphScheduler
from utils.config import get_master_config
from utils.logs import set_logging_level
from graph.base_nodes import NodeCollection



MasterJobDescription = namedtuple('MasterJobDescription', ['graph_id', 'job'])


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
        m = None
        with self.server.job_description_queue_lock:
            if worker_message.message_type == WorkerMessageType.HEARTBEAT:
                if self.idle_worker(worker_message):
                    self.server.allocate_job(worker_message)
                m = self.make_aknowledge_message(worker_id)

                if worker_message.body and worker_id in self.server.worker_to_job_description:
                    graph_id = self.server.worker_to_job_description[worker_id].graph_id
                    with self.server.new_schedulers_lock:
                        scheduler = self.server.graph_id_to_scheduler[graph_id]
                        if worker_message.run_status == RunStatus.RUNNING:
                            worker_message.body.node.node_running_status = NodeRunningStatus.RUNNING
                            scheduler.update_node(worker_message.body.node)

            elif worker_message.message_type == WorkerMessageType.GET_JOB and worker_id in self.server.worker_to_job_description:
                m = MasterMessage(
                    worker_id=worker_id,
                    message_type=MasterMessageType.SET_JOB,
                    job=self.server.worker_to_job_description[worker_id].job,
                    graph_id=self.server.worker_to_job_description[worker_id].graph_id
                    )
                logging.info("SET_JOB worker_id: {}".format(worker_id))
            elif worker_message.message_type == WorkerMessageType.JOB_FINISHED_SUCCESS:
                job = self.server.worker_to_job_description[worker_id].job
                graph_id = self.server.worker_to_job_description[worker_id].graph_id
                assert job.node._id == worker_message.body.node._id
                with self.server.new_schedulers_lock:
                    scheduler = self.server.graph_id_to_scheduler[graph_id]

                worker_message.body.node.node_running_status = NodeRunningStatus.SUCCESS
                scheduler.update_node(worker_message.body.node)
                #scheduler._set_node_status(job._id, NodeRunningStatus.SUCCESS)

                logging.info("Job `{}` marked as SUCCESSFUL".format(job.node._id))
                if worker_id in self.server.worker_to_job_description:
                    del self.server.worker_to_job_description[worker_id]
                m = self.make_aknowledge_message(worker_id)

            elif worker_message.message_type == WorkerMessageType.JOB_FINISHED_FAILED:
                job = self.server.worker_to_job_description[worker_id].job
                graph_id = self.server.worker_to_job_description[worker_id].graph_id
                assert job.node._id == worker_message.body.node._id
                with self.server.new_schedulers_lock:
                    scheduler = self.server.graph_id_to_scheduler[graph_id]

                worker_message.body.node.node_running_status = NodeRunningStatus.FAILED
                scheduler.update_node(worker_message.body.node)
                #scheduler.set_node_status(job._id, NodeRunningStatus.FAILED)

                logging.info("Job `{}` marked as FAILED".format(job.node._id))
                if worker_id in self.server.worker_to_job_description:
                    del self.server.worker_to_job_description[worker_id]
                m = self.make_aknowledge_message(worker_id)

        if m:
            send_msg(self.request, m)

        with self.server.job_description_queue_lock:
            logging.info('Queue size: {}'.format(len(self.server.job_description_queue)))
        
        # Respond with AKN
        #self.request.sendall(worker_message)

    @staticmethod
    def idle_worker(worker_message):
        return worker_message.run_status == RunStatus.IDLE

    @staticmethod
    def make_aknowledge_message(worker_id):
        return MasterMessage(
            worker_id=worker_id,
            message_type=MasterMessageType.AKNOWLEDGE,
            job=None,
            graph_id=None
            )


class MasterTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    # Ctrl-C will cleanly kill all spawned threads
    daemon_threads = True
    # much faster rebinding
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)
        self.alive = True
        self.graph_collection_manager = GraphCollectionManager()
        self.job_description_queue = deque()
        self.job_description_queue_lock = threading.Lock()
        self.worker_to_job_description = {}
        self.node_collection = NodeCollection()

        running_graphs = self.graph_collection_manager.get_graphs(GraphRunningStatus.RUNNING)
        if len(running_graphs) > 0:
            logging.info("Found {} running graphs. Setting them to 'READY'".format(len(running_graphs)))
            for graph in running_graphs:
                graph.graph_running_status = GraphRunningStatus.READY
                for node in graph.nodes:
                    if node.node_running_status == NodeRunningStatus.RUNNING:
                        node.node_running_status = NodeRunningStatus.CREATED
                graph.save()

        self.graph_id_to_scheduler = {}
        self.new_graph_id_to_scheduler = []
        self.new_schedulers_lock = threading.Lock()

        self.thread_db_status_update = threading.Thread(target=self.run_db_status_update, args=())
        self.thread_db_status_update.daemon = True   # Daemonize thread
        self.thread_db_status_update.start()

        self.thread_scheduler = threading.Thread(target=self.run_scheduler, args=())
        self.thread_scheduler.daemon = True   # Daemonize thread
        self.thread_scheduler.start()

    def allocate_job(self, worker_message):
        if len(self.job_description_queue) == 0:    # No jobs to allocate
            return False
        if worker_message.worker_id in self.worker_to_job_description:   # worker already has a job
            return False
        while self.job_description_queue:
            job_description = self.job_description_queue.popleft()
            scheduler = self.graph_id_to_scheduler.get(job_description.graph_id, None)
            if scheduler and scheduler.graph.graph_running_status == GraphRunningStatus.RUNNING:
                self.worker_to_job_description[worker_message.worker_id] = job_description
                return True
        return False

    def run_db_status_update(self):
        while self.alive:
            graphs = self.graph_collection_manager.get_graphs(GraphRunningStatus.READY)
            for graph in graphs:
                graph_scheduler = GraphScheduler(graph, self.node_collection)
                graph_scheduler.graph.graph_running_status = GraphRunningStatus.RUNNING
                graph_scheduler.graph.save()

                with self.new_schedulers_lock:
                    self.new_graph_id_to_scheduler.append(graph_scheduler)

            sleep(1)

    def run_scheduler(self):
        while self.alive:
            with self.new_schedulers_lock:
                self.graph_id_to_scheduler.update(
                    {
                    graph_scheduler.graph._id: graph_scheduler for graph_scheduler in self.new_graph_id_to_scheduler
                    })
                self.new_graph_id_to_scheduler = []

            new_to_queue = []
            finished_graph_ids = []
            for graph_id, scheduler in self.graph_id_to_scheduler.iteritems():
                if scheduler.finished():
                    finished_graph_ids.append(graph_id)
                    continue
                new_to_queue.extend(
                    [MasterJobDescription(graph_id=graph_id, job=job) for job in scheduler.pop_jobs()])

            for graph_id in finished_graph_ids:
                del self.graph_id_to_scheduler[graph_id]

            with self.job_description_queue_lock:
                self.job_description_queue.extend(new_to_queue)

            sleep(1)


def parse_arguments():
    parser = argparse.ArgumentParser(description='Master launcher')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_arguments()
    set_logging_level(args.verbose)

    master_config = get_master_config()
    server = MasterTCPServer((master_config.host, master_config.port), ClientTCPHandler)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.alive = False
        sys.exit(0)
