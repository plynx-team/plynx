import re
from tempfile import SpooledTemporaryFile
from . import BaseNode
from constants import JobReturnStatus
from utils.file_handler import get_file_stream, upload_file_stream

class Grep(BaseNode):
    def __init__(self, node=None):
        super(self.__class__, self).__init__(node)

    def run(self):
        stream = get_file_stream(self.node.get_input_by_name('in').values[0].resource_id)
        template = self.node.get_parameter_by_name('text').value
        with SpooledTemporaryFile() as f:
            for line in stream:
                if re.search(template, line):
                    f.write(line)
            self.node.get_output_by_name('out').resource_id = upload_file_stream(f)
        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'grep'


if __name__ == "__main__":
    from db import Block, BlockCollectionManager, InputValue
    db_blocks = BlockCollectionManager.get_db_blocks()
    obj_dict = filter(lambda doc: doc['base_block_name'] == Grep.get_base_name(), db_blocks)[-1]

    block = Block()
    block.load_from_dict(obj_dict)
    block.get_input_by_name('in').resource_id='Piton.txt'
    block.get_input_by_name('in').values.append(
        InputValue(
            block_id='fake',
            output_id='fake',
            resource_id='Piton.txt'
            )
        )
    block.get_parameter_by_name('text').value = "def"

    grep = Grep(block)

    grep.run()
    print(grep.block.outputs)