import socket
import sys
import SocketServer
import pickle
import threading
from collections import deque
from time import sleep
from backend.messages import WorkerMessage, RunStatus, WorkerMessageType, MasterMessageType, MasterMessage
from backend.tcp_utils import send_msg, recv_msg
from constants import BlockRunningStatus, GraphRunningStatus
from db.graph_collection_manager import GraphCollectionManager
from graph.graph_scheduler import GraphScheduler
from utils.config import get_master_config
from graph.base_blocks.collection import BlockCollection


class Master:
    def __init__(self):
        pass


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
        with self.server.job_queue_lock:
            if worker_message.message_type == WorkerMessageType.HEARTBEAT:
                if self.idle_worker(worker_message):
                    self.server.allocate_job(worker_message)
                m = self.make_aknowledge_message(worker_id)
            elif worker_message.message_type == WorkerMessageType.GET_JOB and worker_id in self.server.worker_to_job:
                print("SET_JOB")
                m = MasterMessage(
                    worker_id=worker_id,
                    message_type=MasterMessageType.SET_JOB,
                    job=self.server.worker_to_job[worker_id]
                    )
            elif worker_message.message_type == WorkerMessageType.JOB_FINISHED_SUCCESS:
                job = self.server.worker_to_job[worker_id]
                with self.server.new_schedulers_lock:
                    scheduler = self.server.graph_id_to_scheduler[job.graph_id]
                    job._id = job.block_id
                scheduler.set_block_status(worker_message.body, BlockRunningStatus.SUCCESS)

                print("Job marked as successful")
                if worker_id in self.server.worker_to_job:
                    del self.server.worker_to_job[worker_id]
                m = self.make_aknowledge_message(worker_id)

            elif worker_message.message_type == WorkerMessageType.JOB_FINISHED_FAILED:
                job = self.server.worker_to_job[worker_id]
                with self.server.new_schedulers_lock:
                    scheduler = self.server.graph_id_to_scheduler[job.graph_id]
                    job._id = job.block_id
                scheduler.set_block_status(worker_message.body, BlockRunningStatus.FAILED)

                print("Job marked as failed")
                if worker_id in self.server.worker_to_job:
                    del self.server.worker_to_job[worker_id]
                m = self.make_aknowledge_message(worker_id)

        if m:
            send_msg(self.request, m)

        with self.server.job_queue_lock:
            print(self.server.job_queue)
        
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
            job=None
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
        self.job_queue = deque()
        self.job_queue_lock = threading.Lock()
        self.worker_to_job = {}
        self.block_collection = BlockCollection()

        running_graphs = self.graph_collection_manager.get_graphs(GraphRunningStatus.RUNNING)
        if len(running_graphs) > 0:
            print("Found {} running graphs. Setting them to 'READY'".format(len(running_graphs)))
            for graph in running_graphs:
                graph.graph_running_status = GraphRunningStatus.READY
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
        if len(self.job_queue) == 0:    # No jobs to allocate
            return False
        if worker_message.worker_id in self.worker_to_job:   # worker already has a job
            return False
        job = self.job_queue.popleft()
        self.worker_to_job[worker_message.worker_id] = job

        return True

    def run_db_status_update(self):
        while self.alive:
            graphs = self.graph_collection_manager.get_graphs(GraphRunningStatus.READY)
            for graph in graphs:
                graph_scheduler = GraphScheduler(graph, self.block_collection)
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
            for graph_id, scheduler in self.graph_id_to_scheduler.iteritems():
                new_to_queue.extend(scheduler.pop_jobs())
                for job in new_to_queue:
                    print job.graph_id

            with self.job_queue_lock:
                self.job_queue.extend(new_to_queue)

            sleep(1)


if __name__ == "__main__":
    master_config = get_master_config()
    #run_server(master_config.host, master_config.port)
    server = MasterTCPServer((master_config.host, master_config.port), ClientTCPHandler)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.alive = False
        sys.exit(0)
