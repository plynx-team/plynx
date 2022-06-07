"""Executors supporting PLynx sync/async inference framework"""
import functools
import os
import shutil
import uuid

import plynx.db.run_cancellation_manager
from plynx.base.executor import BaseExecutor, RunningStatus
from plynx.constants import Collections
from plynx.db.node import Node


@functools.lru_cache()
def run_cancellation_manager():
    """Lazy RunCancellationManager object"""
    return plynx.db.run_cancellation_manager.RunCancellationManager()


class PLynxAsyncExecutor(BaseExecutor):
    """Base Executor class that is using PLynx Async Inference backend"""

    def launch(self) -> RunningStatus:
        """Put the Node on the queue"""
        assert self.node, "`node` in PLynxAsyncExecutor object is not defined"
        self.node.save(collection=Collections.RUNS)
        return RunningStatus(self.node.node_running_status)

    def kill(self):
        run_cancellation_manager().cancel_run(self.node._id)

    def get_running_status(self) -> RunningStatus:
        """Returns the status of the execution.

        Async executions should sync with the remote and return the result immediately.
        """
        assert self.node, "node must be defined at this point"
        self.node = Node.load(self.node._id, collection=Collections.RUNS)
        return RunningStatus(self.node.node_running_status)


class PLynxSyncExecutor(BaseExecutor):
    """Base Executor class that is using PLynx Sync Inference backend"""

    def launch(self) -> RunningStatus:
        """Run the node now and return the status"""
        assert self.node, "node must be defined at this point"
        self.run()
        return RunningStatus(self.node.node_running_status)


class PLynxAsyncExecutorWithDirectory(PLynxAsyncExecutor):
    """Base Executor class that is using PLynx Async Inference backend"""

    def __init__(self, node):
        super().__init__(node)
        self.workdir = os.path.join('/tmp', str(uuid.uuid1()))

    def init_executor(self):
        """Make tmp dir if it does not exist"""
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)

    def clean_up_executor(self):
        """Remove tmp dir"""
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir, ignore_errors=True)
