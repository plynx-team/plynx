from . import BaseNode
from constants import JobReturnStatus

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


if __name__ == "__main__":
    from db import Block, BlockCollectionManager
    db_blocks = BlockCollectionManager.get_db_blocks()
    obj_dict = filter(lambda doc: doc['base_block_name'] == GetResource.get_base_name(), db_blocks)[-1]

    block = Block()
    block.load_from_dict(obj_dict)
    block.get_parameter_by_name('resource_id').value = "Piton.txt"

    get_resource = GetResource(block)

    get_resource.run()
    print(get_resource.block.outputs)