from plynx.graph.base_nodes import BaseNode
from plynx.constants import JobReturnStatus, NodeStatus, FileTypes, ParameterTypes
from plynx.db import Node, Output, Parameter


class GetResource(BaseNode):
    def __init__(self, node=None):
        super(self.__class__, self).__init__(node)

    def run(self):
        self.node.get_output_by_name('out').resource_id = self.node.get_parameter_by_name('resource_id').value
        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'get_resource'

    @classmethod
    def get_default(cls):
        node = Node()
        node.title = ''
        node.description = ''
        node.base_node_name = cls.get_base_name()
        node.node_status = NodeStatus.CREATED
        node.starred = False
        node.parameters = [
            Parameter(
                name='resource_id',
                parameter_type=ParameterTypes.STR,
                value='hello',
                mutable_type=False,
                publicable=True,
                removable=False
            )
        ]
        node.outputs = [
            Output(
                name='out',
                file_type=FileTypes.FILE,
                resource_id=None
            )
        ]
        return node
