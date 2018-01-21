from . import BlockBase
from constants import JobReturnStatus
from tempfile import SpooledTemporaryFile
from utils.file_handler import upload_file_stream

class Echo(BlockBase):
    def __init__(self, block=None):
        super(self.__class__, self).__init__(block)

    def run(self):
        with SpooledTemporaryFile() as f:
            f.write(self.block.get_parameter_by_name('text').value + '\n')
            self.block.get_output_by_name('out').resource_id = upload_file_stream(f)
        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'echo'


if __name__ == "__main__":
    from db import Block, BlockCollectionManager
    db_blocks = BlockCollectionManager.get_db_blocks()
    echo_dict = filter(lambda doc: doc['base_block_name'] == 'echo', db_blocks)[-1]

    block = Block()
    block.load_from_dict(echo_dict)
    block.get_parameter_by_name('text').value = "Hello world"

    echo = Echo(block)

    #echo.parameters['text'] = {'type': 'str', 'value': 'Hello world'}

    echo.run()
    print echo.block.outputs
