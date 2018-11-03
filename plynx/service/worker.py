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
from plynx.constants import JobReturnStatus
from plynx.utils.file_handler import upload_file_stream
from plynx.utils.logs import set_logging_level


DEFAULT_HOST, DEFAULT_PORT = "127.0.0.1", 10000
HEARTBEAT_TIMEOUT = 1
ATTEMPT_TO_CONNECT_TIMEOUT = 1
RUNNER_TIMEOUT = 1


class RunningPipelineException(Exception):
    pass


class Worker:
    NUMBER_OF_ATTEMPTS = 10

    def __init__(self, worker_id, host, port):
        self._run_thread = threading.Thread(target=self.run, args=())
        self._run_thread.daemon = True   # Daemonize thread
        self._job = None
        self._graph_id = None
        self._alive = True
        self._worker_id = worker_id
        self._host = host
        self._port = port
        self._run_status = RunStatus.IDLE
        self._job_killed = False

    def attempt_to_connect(self, number_of_attempts=NUMBER_OF_ATTEMPTS):
        for attempt in range(number_of_attempts):
            try:
                self.heartbeat_iteration()
            except KeyboardInterrupt:
                sys.exit(0)
            except:
                logging.info("Failed to connect: #{} / #{}".format(attempt + 1, number_of_attempts))
                sleep(ATTEMPT_TO_CONNECT_TIMEOUT)
            else:
                logging.info("Connected")
                return True
        return False

    def forever(self):
        #Run run() method
        self._run_thread.start()

        # run heartbeat_iteration() method
        while self._alive:
            try:
                self.heartbeat_iteration()
                sleep(HEARTBEAT_TIMEOUT)
            except KeyboardInterrupt:
                sys.exit(0)

    def heartbeat_iteration(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # Connect to server and send data
            sock.connect((self._host, self._port))
            message = WorkerMessage(
                worker_id=self._worker_id,
                run_status=self._run_status,
                message_type=WorkerMessageType.HEARTBEAT,
                body=self._job if self._run_status != RunStatus.IDLE else None,
                graph_id=self._graph_id
            )
            send_msg(sock, message)
            master_message = recv_msg(sock)
            # check status
            if master_message.message_type == MasterMessageType.KILL:
                logging.info("Received KILL message: {}".format(master_message))
                if self._job and not self._job_killed:
                    self._job_killed = True
                    self._job.kill()
                else:
                    logging.info("Already attempted to KILL")
        finally:
            sock.close()

    def run(self):
        while True:
            logging.info(self._run_status)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                if self._run_status == RunStatus.IDLE:
                    sock.connect((self._host, self._port))
                    message = WorkerMessage(
                        worker_id=self._worker_id,
                        run_status=self._run_status,
                        message_type=WorkerMessageType.GET_JOB,
                        body=None,
                        graph_id=None
                    )
                    send_msg(sock, message)
                    master_message = recv_msg(sock)
                    logging.debug("Asked for a job; Received mesage: {}".format(master_message))
                    if master_message and master_message.message_type == MasterMessageType.SET_JOB:
                        logging.info(
                            "Got the job: graph_id=`{graph_id}` job_id=`{job_id}`".format(
                                graph_id=master_message.graph_id,
                                job_id=master_message.job.node._id,
                            )
                        )
                        self._job_killed = False
                        self._run_status = RunStatus.RUNNING
                        self._job = master_message.job
                        self._graph_id = master_message.graph_id
                        try:
                            status = self._job.run()
                        except Exception as e:
                            try:
                                status = JobReturnStatus.FAILED
                                with SpooledTemporaryFile() as f:
                                    f.write(traceback.format_exc())
                                    self._job.node.get_log_by_name('worker').resource_id = upload_file_stream(f)
                            except Exception as e:
                                self._alive = False
                                logging.critical(traceback.format_exc())
                                sys.exit(1)

                        self._job_killed = True
                        if status == JobReturnStatus.SUCCESS:
                            self._run_status = RunStatus.SUCCESS
                        elif status == JobReturnStatus.FAILED:
                            self._run_status = RunStatus.FAILED
                        logging.info("WorkerMessageType.FINISHED with status {}".format(self._run_status))

                elif self._run_status == RunStatus.RUNNING:
                    raise RunningPipelineException("Not supposed to have this state")
                elif self._run_status in [RunStatus.SUCCESS, RunStatus.FAILED]:
                    sock.connect((self._host, self._port))

                    if self._run_status == RunStatus.SUCCESS:
                        status = WorkerMessageType.JOB_FINISHED_SUCCESS
                    elif self._run_status == RunStatus.FAILED:
                        status = WorkerMessageType.JOB_FINISHED_FAILED

                    message = WorkerMessage(
                        worker_id=self._worker_id,
                        run_status=self._run_status,
                        message_type=status,
                        body=self._job,
                        graph_id=self._graph_id
                    )

                    send_msg(sock, message)

                    master_message = recv_msg(sock)

                    if master_message and master_message.message_type == MasterMessageType.AKNOWLEDGE:
                        self._run_status = RunStatus.IDLE
                        logging.info("WorkerMessageType.IDLE")
            finally:
                sock.close()

            sleep(RUNNER_TIMEOUT)


def run_worker(worker_id=None, verbose=0, host=DEFAULT_HOST, port=DEFAULT_PORT):
    set_logging_level(verbose)
    if worker_id is None:
        worker_id = str(uuid.uuid1())
    worker = Worker(worker_id, host, port)

    if not worker.attempt_to_connect():
        sys.exit(2)

    worker.forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run worker')
    parser.add_argument('-i', '--worker-id', help='Any string identificator')
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument('-H', '--host', default=DEFAULT_HOST)
    parser.add_argument('-P', '--port', default=DEFAULT_PORT)
    args = parser.parse_args()

    run_worker(**vars(args))
