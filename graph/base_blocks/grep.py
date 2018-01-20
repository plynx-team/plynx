import re
from tempfile import SpooledTemporaryFile
from graph.base_blocks.block_base import BlockBase
from constants import JobReturnStatus
from utils.file_handler import get_file_stream, upload_file_stream

class Grep(BlockBase):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.inputs = {'in': {'type': 'file', 'value': None}}
        self.outputs = {'out': {'type': 'file', 'value': None}}
        self.parameters = {'text': {'type': 'str', 'value': ''}}
        self.logs = {
            'stderr': {'type': 'file', 'value': None},
            'stdout': {'type': 'file', 'value': None},
            'worker': {'type': 'file', 'value': None}
        }

    def run(self):
        stream = get_file_stream(self.inputs['in'])
        template = self.parameters['text']['value']
        with SpooledTemporaryFile() as f:
            for line in stream:
                if re.search(template, line):
                    f.write(line)
            self.outputs['out']['value'] = upload_file_stream(f)
        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'grep'


if __name__ == "__main__":
    grep = Grep()
    grep.inputs['in'] = 'Piton.txt'
    grep.parameters['text'] = {'type': 'str', 'value': 'def.txt'}

    grep.run()
    print grep.outputs
