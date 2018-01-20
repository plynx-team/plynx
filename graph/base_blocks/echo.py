from graph.base_blocks.block_base import BlockBase
from constants import JobReturnStatus
from tempfile import SpooledTemporaryFile
from utils.file_handler import upload_file_stream

class Echo(BlockBase):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.outputs = {'out': {'type': 'str', 'value': ''}}
        self.parameters = {'text': {'type': 'str', 'value': ''}}
        self.logs = {
            'stderr': {'type': 'file', 'value': None},
            'stdout': {'type': 'file', 'value': None},
            'worker': {'type': 'file', 'value': None}
        }

    def run(self):
        with SpooledTemporaryFile() as f:
            f.write(self.parameters['text']['value'] + '\n')
            self.outputs['out']['value'] = upload_file_stream(f)
        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'echo'


if __name__ == "__main__":
    echo = Echo()
    echo.parameters['text'] = {'type': 'str', 'value': 'Hello world'}

    echo.run()
    print echo.outputs
