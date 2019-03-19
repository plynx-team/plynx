from plynx.graph.base_nodes import BaseNode
from plynx.constants import JobReturnStatus, NodeStatus, NodeRunningStatus, FileTypes
from plynx.db import Node, Output


class File(BaseNode):
    def __init__(self, node=None):
        super(self.__class__, self).__init__(node)

    def run(self):
        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'file'

    @classmethod
    def get_default(cls):
        node = Node()
        node.title = 'File'
        node.description = 'Custom file'
        node.base_node_name = cls.get_base_name()
        node.node_status = NodeStatus.READY
        node.node_running_status = NodeRunningStatus.STATIC
        node.starred = False
        node.parameters = []
        node.outputs = [
            Output(
                name='out',
                file_type=FileTypes.FILE,
                resource_id=None
            )
        ]
        return node
