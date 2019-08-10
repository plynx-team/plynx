from plynx.graph.base_nodes import BaseNode
from plynx.constants import JobReturnStatus, NodeStatus, NodeRunningStatus
from plynx.db.node import Node
from plynx.db.output import Output
from plynx.plugins.resources import File as FileCls


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
            Output.from_dict({
                'name': 'out',
                'file_type': FileCls.NAME,
                'resource_id': None,
            })
        ]
        return node
