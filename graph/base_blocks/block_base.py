from abc import ABCMeta, abstractmethod

class abstractstatic(staticmethod):
    __slots__ = ()
    def __init__(self, function):
        super(abstractstatic, self).__init__(function)
        function.__isabstractmethod__ = True
    __isabstractmethod__ = True


class BlockBase:
    __metaclass__ = ABCMeta

    # Methods

    def __init__(self):
        self.block_id = None
        self.inputs = None
        self.outputs = None
        self.parameters = None
        self.logs = None
        self.graph_id = None

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

    def restore_from_dict(self, block_with_inputs):
        self.block_id = block_with_inputs._id
        self.inputs = block_with_inputs.inputs
        self.outputs = block_with_inputs.outputs
        self.parameters = block_with_inputs.parameters
