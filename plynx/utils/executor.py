"""Utils to work with executors"""
import json
import logging
import threading
import time
import traceback
from typing import Any, Dict, Union

import requests
import six

import plynx.db.node
import plynx.utils.exceptions
import plynx.utils.plugin_manager
from plynx.base.executor import BaseExecutor
from plynx.constants import NodeRunningStatus
from plynx.utils.common import JSONEncoder
from plynx.utils.config import get_web_config
from plynx.utils.file_handler import upload_file_stream

CONNECT_POST_TIMEOUT = 1.0
REQUESTS_TIMEOUT = 10


def urljoin(base: str, postfix: str) -> str:
    """Join urls in a reasonable way"""
    if base[-1] == "/":
        return f"{base}{postfix}"
    return f"{base}/{postfix}"


def post_request(uri, data, num_retries=3):
    """Make post request to the url"""
    url = urljoin(get_web_config().internal_endpoint, uri)
    json_data = JSONEncoder().encode(data)
    for iter_num in range(num_retries):
        if iter_num != 0:
            time.sleep(CONNECT_POST_TIMEOUT)
        response = requests.post(url=url, data=json_data, timeout=REQUESTS_TIMEOUT)
        if response.ok:
            return json.loads(response.text)
    return None


def _update_node(node: plynx.db.node.Node):
    """Update node in the database"""
    resp = post_request("update_run", data={"node": node.to_dict()})
    logging.info(f"Run update res: {resp}")


def materialize_executor(node: Union[Dict[str, Any], plynx.db.node.Node]) -> BaseExecutor:
    """
    Create a Node object from a dictionary

    Parameters:
        node: dictionary representation of a Node or the node itself

    Returns:
        Executor: Executor based on the kind of the Node and the config
    """

    if isinstance(node, dict):
        node = plynx.db.node.Node.from_dict(node)
    cls = plynx.utils.plugin_manager.get_executor_manager().kind_to_executor_class.get(node.kind)
    if not cls:
        raise plynx.utils.exceptions.ExecutorNotFound(
            f"Node kind `{node.kind}` not found"
        )
    return cls(node)


class TickThread:
    """
    This class is a Context Manager wrapper.
    It calls method `tick()` of the executor with a given interval
    """

    TICK_TIMEOUT: int = 1

    def __init__(self, executor: BaseExecutor):
        self.executor = executor
        self._stop_event = threading.Event()
        self._tick_thread = threading.Thread(target=self.call_executor_tick, args=())

    def __enter__(self):
        """
        Currently no meaning of returned class
        """
        self._tick_thread.start()
        return self

    def __exit__(self, type_cls, value, traceback_val):
        self._stop_event.set()

    def call_executor_tick(self):
        """Run timed ticks"""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=TickThread.TICK_TIMEOUT)
            if self.executor.is_updated() and not self._stop_event.is_set():
                # Save logs when operation is running
                if NodeRunningStatus.is_finished(self.executor.node.node_running_status):
                    break
                _update_node(self.executor.node)


class DBJobExecutor:
    """Executes a single job in an executor and updates its status."""

    def __init__(self, executor: BaseExecutor):
        assert executor.node, "Executor has no `node` attribute defined"
        self.executor = executor
        self._killed = False

    def run(self) -> str:
        """Run the job in the executor"""
        assert self.executor.node, "Executor has no `node` attribute defined"

        try:
            try:
                status = NodeRunningStatus.FAILED
                self.executor.init_executor()
                with TickThread(self.executor):
                    status = self.executor.run()
            except Exception:   # pylint: disable=broad-except
                try:
                    f = six.BytesIO()
                    f.write(traceback.format_exc().encode())
                    worker_log = self.executor.node.get_log_by_name(name="worker")
                    worker_log.values = [upload_file_stream(f)]
                    logging.error(traceback.format_exc())
                except Exception:   # pylint: disable=broad-except
                    # This case of `except` has happened before due to I/O failure
                    logging.critical(traceback.format_exc())
                    raise
            finally:
                self.executor.clean_up_executor()

            logging.info(f"Node {self.executor.node._id} `{self.executor.node.title}` finished with status `{status}`")
            self.executor.node.node_running_status = status
        except Exception as e:  # pylint: disable=broad-except
            logging.warning(f"Execution failed: {e}")
            self.executor.node.node_running_status = NodeRunningStatus.FAILED
        finally:
            _update_node(self.executor.node)

            self._killed = True

        return status

    def kill(self) -> None:
        """Kill the running job"""
        assert self.executor.node, "Executor has no `node` attribute defined"
        if self._killed:
            return
        if NodeRunningStatus.is_finished(self.executor.node.node_running_status):
            self.executor.kill()
        self._killed = True
