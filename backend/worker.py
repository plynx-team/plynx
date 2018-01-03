import argparse
import logging
import socket
import sys
import uuid
import threading
import traceback
from time import sleep
from tempfile import SpooledTemporaryFile
from backend.messages import WorkerMessage, WorkerMessageType, RunStatus, MasterMessageType
from backend.tcp_utils import send_msg, recv_msg
from constants import JobReturnStatus
from utils.file_handler import upload_file_stream


HOST, PORT = "localhost", 10000

# Create a socket (SOCK_STREAM means a TCP socket)


class RunningPipelineException(Exception):
    pass

class Worker:
    def __init__(self):
        self.thread = threading.Thread(target=self.run, args=())
        self.thread.daemon = True   # Daemonize thread
        self.job = None
        self.alive = True
        self.worker_id = None
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
            sock.connect((HOST, PORT))
            m = WorkerMessage(
                worker_id=self.worker_id,
                run_status=self.run_status,
                message_type=WorkerMessageType.HEARTBEAT,
                body=None
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
                    sock.connect((HOST, PORT))
                    m = WorkerMessage(
                        worker_id=self.worker_id,
                        run_status=self.run_status,
                        message_type=WorkerMessageType.GET_JOB,
                        body=None
                        )
                    send_msg(sock, m)
                    master_message = recv_msg(sock)
                    print("Ask For job: ", master_message)
                    if master_message and master_message.message_type == MasterMessageType.SET_JOB:
                        print("Got the job")
                        self.run_status = RunStatus.RUNNING
                        self.job = master_message.job
                        try:
                            status = self.job.run()
                        except Exception as e:
                            try:
                                status = JobReturnStatus.FAILED
                                with SpooledTemporaryFile() as f:
                                    f.write(traceback.format_exc())
                                    self.job.logs['worker'] = upload_file_stream(f)
                            except Exception as e:
                                self.alive = False
                                logging.critical(traceback.format_exc())
                                sys.exit(1)

                        if status == JobReturnStatus.SUCCESS:
                            self.run_status = RunStatus.SUCCESS
                        elif status == JobReturnStatus.FAILED:
                            self.run_status = RunStatus.FAILED
                        print("WorkerMessageType.FINISHED", self.run_status)

                elif self.run_status == RunStatus.RUNNING:
                    raise RunningPipelineException("Not supposed to have this state")
                elif self.run_status in [RunStatus.SUCCESS, RunStatus.FAILED]:
                    sock.connect((HOST, PORT))

                    if self.run_status == RunStatus.SUCCESS:
                        status = WorkerMessageType.JOB_FINISHED_SUCCESS
                    elif self.run_status == RunStatus.FAILED:
                        status = WorkerMessageType.JOB_FINISHED_FAILED

                    m = WorkerMessage(
                        worker_id=self.worker_id,
                        run_status=self.run_status,
                        message_type=status,
                        body=self.job
                        )

                    send_msg(sock, m)

                    master_message = recv_msg(sock)

                    if master_message and master_message.message_type == MasterMessageType.AKNOWLEDGE:
                        self.run_status = RunStatus.IDLE
                        print("WorkerMessageType.IDLE")

            finally:
                sock.close()

            sleep(1)


def run_worker(worker_id=None):
    if worker_id is None:
        worker_id = str(uuid.uuid1())
    worker = Worker()
    worker.worker_id = worker_id

    worker.forever()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run worker.')
    parser.add_argument('-i', '--worker-id', help='Any string identificator')
    args = parser.parse_args()

    run_worker(**vars(args))