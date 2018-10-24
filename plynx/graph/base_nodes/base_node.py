from abc import ABCMeta, abstractmethod


class abstractstatic(staticmethod):
    __slots__ = ()

    def __init__(self, function):
        super(abstractstatic, self).__init__(function)
        function.__isabstractmethod__ = True
    __isabstractmethod__ = True


class BaseNode:
    __metaclass__ = ABCMeta

    # Methods

    def __init__(self, node):
        self.node = node

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

    @classmethod
    def get_default(cls):
        pass
