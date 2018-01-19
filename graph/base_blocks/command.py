from graph.base_blocks.block_base import BlockBase
from constants import JobReturnStatus
from utils.file_handler import upload_file_stream
import subprocess
import os
import json

class Command(BlockBase):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.parameters = {'cmd': ''}
        self.logs = {'stderr': '', 'stdout': '', 'worker':''}

    def run(self):
        env = os.environ.copy()
        cmd_array = [
            self._get_arguments_string('input', self.inputs),
            self._get_arguments_string('output', self.outputs),
            self._get_arguments_string('param', self.parameters),
            self.parameters['cmd']
        ]
        print "----"
        print ';'.join(cmd_array)
        print "----"
        subprocess.call(';'.join(cmd_array), shell=True, env=env, executable='bash')

        return JobReturnStatus.SUCCESS

    def status(self):
        pass

    def kill(self):
        pass

    @staticmethod
    def get_base_name():
        return 'command'

    @staticmethod
    def _get_arguments_string(var_name, arguments):
        res = []
        res.append('declare -A {}'.format(var_name))
        for key, value in arguments.iteritems():
            res.append('{}["{}"]={}'.format(var_name, key, Command._escape_bash(value)))
        return ';'.join(res)

    @staticmethod
    def _escape_bash(s):
        return json.dumps(s).replace("'", "\\'")


if __name__ == "__main__":
    command = Command()

    command.block_id = 'abc',
    command.inputs = { "in" : "" }
    command.outputs = { "out" : "" }

    command.parameters = { "text" : "hello I'm Vanya", 'cmd': 'bash -c "echo abc ${param[text]}"'}

    command.run()
