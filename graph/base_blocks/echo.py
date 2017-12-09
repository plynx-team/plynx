from graph.base_blocks.block_base import BlockBase, JobReturnStatus
from tempfile import SpooledTemporaryFile
from utils.file_handler import upload_file_stream

class Echo(BlockBase):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.outputs = {'out': ''}
        self.parameters = {'text': ''}
        self.logs = {'stderr': '', 'stdout': '', 'worker':''}

    def run(self):
        with SpooledTemporaryFile() as f:
            f.write(self.parameters['text'] + '\n')
            self.outputs['out'] = upload_file_stream(f)
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
    echo.parameters['text'] = 'Hello world'

    echo.run()
    print echo.outputs
