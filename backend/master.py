import socket
import sys
import SocketServer
import pickle
import threading
from utils.config import get_master_config
from backend.messages import WorkerMessage, RunStatus, WorkerMessageType, MasterMessageType, MasterMessage
from backend.tcp_utils import send_msg, recv_msg
from collections import deque

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
                print("Job marked as successful")
                if worker_id in self.server.worker_to_job:
                    del self.server.worker_to_job[worker_id]
                m = self.make_aknowledge_message(worker_id)
            elif worker_message.message_type == WorkerMessageType.JOB_FINISHED_FAILED:
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

    job_queue = deque()
    job_queue_lock = threading.Lock()
    worker_to_job = {}

    def __init__(self, server_address, RequestHandlerClass):
        SocketServer.TCPServer.__init__(self, server_address, RequestHandlerClass)

        col = BlockCollection()
        self.job_queue.append(col.name_to_class['echo']())
        self.job_queue[-1].parameters['text'] = "echo 1"
        self.job_queue.append(col.name_to_class['echo']())
        self.job_queue[-1].parameters['text'] = "echo 2"
        print(self.job_queue)
        print self.job_queue[-1].__dict__
        from graph.base_blocks.echo import Echo
        e = Echo()
        print e.__dict__
        # print e.__getstate__()

    def allocate_job(self, worker_message):
        if len(self.job_queue) == 0:    # No jobs to allocate
            return False
        if worker_message.worker_id in self.worker_to_job:   # worker already has a job
            return False
        job = self.job_queue.popleft()
        self.worker_to_job[worker_message.worker_id] = job

        return True


if __name__ == "__main__":
    master_config = get_master_config()
    #run_server(master_config.host, master_config.port)
    server = MasterTCPServer((master_config.host, master_config.port), ClientTCPHandler)

    # Activate the server; this will keep running until you
    # interrupt the program with Ctrl-C
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.exit(0)
