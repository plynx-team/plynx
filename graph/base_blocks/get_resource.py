from graph.base_blocks.block_base import BlockBase, JobReturnStatus

class GetResource(BlockBase):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.outputs = {'out': ''}
        self.parameters = {'resource_id': ''}
        self.logs = {'stderr': '', 'stdout': '', 'worker':''}

    def run(self):
        self.outputs['out'] = self.parameters['resource_id']
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
    get_resource.parameters['resource_id'] = 'Piton.txt'

    get_resource.run()
    print get_resource.outputs
