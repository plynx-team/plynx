from . import BlockBase
from constants import JobReturnStatus

class GetResource(BlockBase):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.outputs = {'out': {'type': 'file', 'value': None}}
        self.parameters = {'resource_id': {'type': 'str', 'value': ''}}
        self.logs = {
            'stderr': {'type': 'file', 'value': None},
            'stdout': {'type': 'file', 'value': None},
            'worker': {'type': 'file', 'value': None}
        }

    def run(self):
        self.outputs['out']['value'] = self.parameters['resource_id']['value']
        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'get_resource'


if __name__ == "__main__":
    get_resource = GetResource()
    get_resource.parameters['resource_id'] = {'type': 'str', 'value': 'Piton.txt'}

    get_resource.run()
    print get_resource.outputs
