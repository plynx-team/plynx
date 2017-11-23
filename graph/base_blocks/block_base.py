from abc import ABCMeta, abstractmethod

class BlockBase:
    __metaclass__ = ABCMeta

    # Properties

    inputs = {}
    outputs = {}
    parameters = {}
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

    @abstractmethod
    def get_base_name(self):
        pass

