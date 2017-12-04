from abc import ABCMeta, abstractmethod
from enum import Enum

class abstractstatic(staticmethod):
    __slots__ = ()
    def __init__(self, function):
        super(abstractstatic, self).__init__(function)
        function.__isabstractmethod__ = True
    __isabstractmethod__ = True


class BlockBase:
    __metaclass__ = ABCMeta

    # Properties

    inputs = None
    outputs = None
    parameters = None
    graph = None

    # Methods

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def status(self):
        pass

    @abstractmethod
    def kill(self):
        pass

    @abstractstatic
    def get_base_name():
        pass


class JobReturnStatus(Enum):
    SUCCESS = 0
    FAILED = 1
