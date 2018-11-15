import logging
import socket
import uuid
import threading
import traceback
from tempfile import SpooledTemporaryFile
from plynx.service import WorkerMessage, WorkerMessageType, RunStatus, MasterMessageType, send_msg, recv_msg
from plynx.constants import JobReturnStatus
from plynx.utils.config import get_master_config
from plynx.utils.file_handler import upload_file_stream


class RunningPipelineException(Exception):
    """Internal Exception which indicates incorrect state of the Worker."""
    pass


class Worker:
    """Worker main class.

    Worker is a service that executes the commands defined by Operations.

    Args:
        worker_id   (str):  An arbitary ID of the worker. It must be unique accross the cluster.
                            If not given or empty, a unique ID will be generated.
        host        (str):  Host of the Master.
        port        (int):  Port of the Master.

    Worker is running in several threads:
        * Main thread: heartbeat iterations.
        * _run_worker thread. It executes the jobs and handles states.

    """

    HEARTBEAT_TIMEOUT = 1
    RUNNER_TIMEOUT = 1
    NUMBER_OF_ATTEMPTS = 10

    def __init__(self, worker_id, host, port):
        if not worker_id:
            worker_id = str(uuid.uuid1())
        self._stop_event = threading.Event()
        self._job = None
        self._graph_id = None
        self._worker_id = worker_id
        self._host = host
        self._port = port
        self._job_killed = False
        self._set_run_status(RunStatus.IDLE)

    def serve_forever(self, number_of_attempts=NUMBER_OF_ATTEMPTS):
        """Run the worker.
        Args:
            number_of_attempts  (int): Number of retries if the connection is not established.
        """
        self._run_thread = threading.Thread(target=self._run_worker, args=())
        self._run_thread.daemon = True   # Daemonize thread
        self._run_thread.start()

        # run _heartbeat_iteration()
        attempt = 0
        while not self._stop_event.is_set():
            try:
                self._heartbeat_iteration()
                if attempt > 0:
                    logging.info("Connected")
                attempt = 0
            except socket.error:
                logging.warn("Failed to connect: #{}/{}".format(attempt + 1, number_of_attempts))
                attempt += 1
                if attempt == number_of_attempts:
                    self.stop()
                    raise
            self._stop_event.wait(timeout=Worker.HEARTBEAT_TIMEOUT)

    def _heartbeat_iteration(self):
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
            if master_message and master_message.message_type == MasterMessageType.KILL:
                logging.info("Received KILL message: {}".format(master_message))
                if self._job and not self._job_killed:
                    self._job_killed = True
                    self._job.kill()
                else:
                    logging.info("Already attempted to KILL")
        finally:
            sock.close()

    def _run_worker(self):
        while not self._stop_event.is_set():
            try:
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
                            self._set_run_status(RunStatus.RUNNING)
                            self._job = master_message.job
                            self._graph_id = master_message.graph_id
                            try:
                                self._job.init_workdir()
                                status = self._job.run()
                            except Exception:
                                try:
                                    status = JobReturnStatus.FAILED
                                    with SpooledTemporaryFile() as f:
                                        f.write(traceback.format_exc())
                                        self._job.node.get_log_by_name('worker').resource_id = upload_file_stream(f)
                                except Exception:
                                    logging.critical(traceback.format_exc())
                                    self.stop()
                            finally:
                                self._job.clean_up()

                            self._job_killed = True
                            if status == JobReturnStatus.SUCCESS:
                                self._set_run_status(RunStatus.SUCCESS)
                            elif status == JobReturnStatus.FAILED:
                                self._set_run_status(RunStatus.FAILED)
                            logging.info(
                                "Worker(`{worker_id}`) finished with status {status}".format(
                                    worker_id=self._worker_id,
                                    status=self._run_status,
                                )
                            )

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
                            self._set_run_status(RunStatus.IDLE)
                finally:
                    sock.close()
            except socket.error:
                pass
            except Exception:
                self.stop()
                raise

            self._stop_event.wait(timeout=Worker.RUNNER_TIMEOUT)

        logging.info("Exit {}".format(self._run_worker.__name__))

    def _set_run_status(self, run_status):
        self._run_status = run_status
        logging.info(self._run_status)

    def stop(self):
        """Stop Worker."""
        self._stop_event.set()


def run_worker(worker_id=None):
    """Run master Daemon. It will run in the same thread.

    Args:
        worker_id   (str):  Worker ID. It will be generated if empty or not given
    """
    master_config = get_master_config()
    logging.info('Init Worker')
    logging.info(master_config)
    worker = Worker(
        worker_id=worker_id,
        host=master_config.host,
        port=master_config.port,
    )

    try:
        worker.serve_forever()
    except KeyboardInterrupt:
        worker.stop()
