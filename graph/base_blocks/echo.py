from graph.base_blocks.block_base import BlockBase

class Echo(BlockBase):
    def __init__(self):
        self.outputs['out'] = ''
        self.parameters['text'] = ''
        pass

    def run(self):
        print(self.parameters['text'])

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
