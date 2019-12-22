import os
import shutil
from abc import abstractmethod


class BaseExecutor:
    def __init__(self, node):
        self.node = node
        self.workdir = None

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def status(self):
        pass

    @abstractmethod
    def kill(self):
        pass

    @staticmethod
    @abstractmethod
    def get_base_name():
        pass

    @staticmethod
    @abstractmethod
    def get_default(cls):
        pass

    def init_workdir(self):
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)

    def clean_up(self):
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir, ignore_errors=True)
