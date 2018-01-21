import subprocess
import os
import json
import uuid
from . import BlockBase
# from Input, InputValue, Output, Parameter
from constants import JobReturnStatus
from utils.file_handler import get_file_stream, upload_file_stream


class Command(BlockBase):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.parameters = {'cmd': {'type': 'str', 'value': ''}}
        self.logs = {
            'stderr': {'type': 'file', 'value': None},
            'stdout': {'type': 'file', 'value': None},
            'worker': {'type': 'file', 'value': None}
        }

    def run(self):
        env = os.environ.copy()
        inputs = Command._prepare_inputs(self.inputs)
        parameters = Command._prepare_parameters(self.parameters)
        outputs = Command._prepare_outputs(self.outputs)
        cmd_array = [
            self._get_arguments_string('input', inputs),
            self._get_arguments_string('output', outputs),
            self._get_arguments_string('param', parameters),
            self.parameters['cmd']['value']
        ]
        print "----"
        print ';'.join(cmd_array)
        print "----"

        subprocess.call(';'.join(cmd_array), shell=True, env=env, executable='bash')

        self._postprocess_outputs(outputs)

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

    @staticmethod
    def _prepare_inputs(inputs):
        res = {}
        for key, input_container in inputs.iteritems():
            filename = os.path.join('/tmp', str(uuid.uuid1()) + '_' + key)
            print filename
            res[key] = filename
            with open(filename, 'wb') as f:
                f.write(get_file_stream(input_container['value']['resource_id']).read())
        return res

    @staticmethod
    def _prepare_outputs(outputs):
        res = {}
        for key, value in outputs.iteritems():
            filename = os.path.join('/tmp', key + str(uuid.uuid1()))
            res[key] = filename
        return res

    @staticmethod
    def _prepare_parameters(parameters):
        res = {}
        for key, parameter in parameters.iteritems():
            res[key] = parameter['value']
        return res

    def _postprocess_outputs(self, outputs):
        for key, filename in outputs.iteritems():
            with open(filename, 'rb') as f:
                self.outputs[key]['value'] = upload_file_stream(f)


if __name__ == "__main__":
    command = Command()

    command.block_id = 'abc',
    command.inputs = {
        "in" : {
            'type': 'file',
            'value': {
                'block_id': '5a',
                'output_id': 'a',
                'resource_id': 'Piton.txt'
            }
        }
    }
    command.outputs = {
        "out" : {
            'type': 'file',
            'value': None
        }
    }
    command.parameters = {
        "text" : {
            'type': 'str',
            'value': 'def'
        },
        "cmd" : {
            'type': 'str',
            'value': 'cat ${input[in]} | grep ${param[text]} > ${output[out]}'
        }
    }
    command.run()
    print(command.outputs)
