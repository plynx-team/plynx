import argparse
import logging
import socket
import sys
import uuid
import threading
import traceback
from time import sleep
from tempfile import SpooledTemporaryFile
from . import WorkerMessage, WorkerMessageType, RunStatus, MasterMessageType, send_msg, recv_msg
from constants import JobReturnStatus
from utils.file_handler import upload_file_stream
from utils.logs import set_logging_level


HOST, PORT = "127.0.0.1", 10000

# Create a socket (SOCK_STREAM means a TCP socket)


class RunningPipelineException(Exception):
    pass

class Worker:
    def __init__(self, worker_id, host, port):
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.daemon = True   # Daemonize thread
        self.job = None
        self.graph_id = None
        self.alive = True
        self.worker_id = worker_id
        self.host = host
        self.port = port
        self.run_status = RunStatus.IDLE

    def forever(self):
        self.thread.start()
        while self.alive:
            try:
                self.heartbeat_iteration()
                sleep(1)
            except KeyboardInterrupt:
                sys.exit(0)
            

    def heartbeat_iteration(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Connect to server and send data
            sock.connect((self.host, self.port))
            m = WorkerMessage(
                worker_id=self.worker_id,
                run_status=self.run_status,
                message_type=WorkerMessageType.HEARTBEAT,
                body=self.job if self.run_status != RunStatus.IDLE else None,
                graph_id=self.graph_id
                )
            send_msg(sock, m)
            resp = recv_msg(sock)
            # TODO Check response
        finally:
            sock.close()

    def run(self):
        while True:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                if self.run_status == RunStatus.IDLE:
                    sock.connect((self.host, self.port))
                    m = WorkerMessage(
                        worker_id=self.worker_id,
                        run_status=self.run_status,
                        message_type=WorkerMessageType.GET_JOB,
                        body=None,
                        graph_id=None
                        )
                    send_msg(sock, m)
                    master_message = recv_msg(sock)
                    logging.info("I asked for a job; Received: {}".format(master_message))
                    if master_message and master_message.message_type == MasterMessageType.SET_JOB:
                        logging.info("Got the job")
                        self.run_status = RunStatus.RUNNING
                        self.job = master_message.job
                        self.graph_id = master_message.graph_id
                        try:
                            status = self.job.run()
                        except Exception as e:
                            try:
                                status = JobReturnStatus.FAILED
                                with SpooledTemporaryFile() as f:
                                    f.write(traceback.format_exc())
                                    self.job.node.get_log_by_name('worker').resource_id = upload_file_stream(f)
                            except Exception as e:
                                self.alive = False
                                logging.critical(traceback.format_exc())
                                sys.exit(1)

                        if status == JobReturnStatus.SUCCESS:
                            self.run_status = RunStatus.SUCCESS
                        elif status == JobReturnStatus.FAILED:
                            self.run_status = RunStatus.FAILED
                        logging.info("WorkerMessageType.FINISHED with status {}".format(self.run_status))

                elif self.run_status == RunStatus.RUNNING:
                    raise RunningPipelineException("Not supposed to have this state")
                elif self.run_status in [RunStatus.SUCCESS, RunStatus.FAILED]:
                    sock.connect((self.host, self.port))

                    if self.run_status == RunStatus.SUCCESS:
                        status = WorkerMessageType.JOB_FINISHED_SUCCESS
                    elif self.run_status == RunStatus.FAILED:
                        status = WorkerMessageType.JOB_FINISHED_FAILED

                    m = WorkerMessage(
                        worker_id=self.worker_id,
                        run_status=self.run_status,
                        message_type=status,
                        body=self.job,
                        graph_id=self.graph_id
                        )

                    send_msg(sock, m)

                    master_message = recv_msg(sock)

                    if master_message and master_message.message_type == MasterMessageType.AKNOWLEDGE:
                        self.run_status = RunStatus.IDLE
                        logging.info("WorkerMessageType.IDLE")

            finally:
                sock.close()

            sleep(1)


def run_worker(worker_id=None, verbose=0, host=None, port=None):
    set_logging_level(verbose)
    host = host or HOST
    port = port or PORT
    if worker_id is None:
        worker_id = str(uuid.uuid1())
    worker = Worker(worker_id, host, port)

    worker.forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run worker')
    parser.add_argument('-i', '--worker-id', help='Any string identificator')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument('-H', '--host', default=HOST)
    parser.add_argument('-P', '--port', default=PORT)
    args = parser.parse_args()

    run_worker(**vars(args))
