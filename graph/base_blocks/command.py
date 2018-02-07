import subprocess
import os
import json
import uuid
import logging
from tempfile import SpooledTemporaryFile
from . import BlockBase
# from Input, InputValue, Output, Parameter
from constants import JobReturnStatus
from utils.file_handler import get_file_stream, upload_file_stream


class Command(BlockBase):
    def __init__(self, block=None):
        super(self.__class__, self).__init__(block)

    def run(self):
        with SpooledTemporaryFile() as worker_log_file:
            env = os.environ.copy()
            inputs = Command._prepare_inputs(self.block.inputs)
            parameters = Command._prepare_parameters(self.block.parameters)
            outputs = Command._prepare_outputs(self.block.outputs)
            cmd_array = [
                self._get_arguments_string('input', inputs),
                self._get_arguments_string('output', outputs),
                self._get_arguments_string('param', parameters),
                self.block.get_parameter_by_name('cmd').value
            ]

            worker_log_file.write(';'.join(cmd_array))
            self.block.get_log_by_name('worker').resource_id = upload_file_stream(worker_log_file)

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
        for input in inputs:
            filenames = []
            print input.values
            for i, value in enumerate(input.values):
                filename = os.path.join('/tmp', '{}_{}_{}'.format(str(uuid.uuid1()), i, input.name))
                with open(filename, 'wb') as f:
                    f.write(get_file_stream(value.resource_id).read())
                filenames.append(filename)
            res[input.name] = ' '.join(filenames)
        return res

    @staticmethod
    def _prepare_outputs(outputs):
        res = {}
        for output in outputs:
            filename = os.path.join('/tmp', '{}_{}'.format(str(uuid.uuid1()), output.name))
            res[output.name] = filename
        return res

    @staticmethod
    def _prepare_parameters(parameters):
        res = {}
        for parameter in parameters:
            res[parameter.name] = parameter.value
        return res

    def _postprocess_outputs(self, outputs):
        for key, filename in outputs.iteritems():
            with open(filename, 'rb') as f:
                self.block.get_output_by_name(key).resource_id = upload_file_stream(f)


if __name__ == "__main__":
    from db import Block, BlockCollectionManager, InputValue
    db_blocks = BlockCollectionManager.get_db_blocks()
    obj_dict = filter(lambda doc: doc['base_block_name'] == Command.get_base_name(), db_blocks)[-1]

    block = Block()
    block.load_from_dict(obj_dict)
    block.get_input_by_name('in').values.append(
        InputValue(
            block_id='fake',
            output_id='fake',
            resource_id='Piton.txt'
            )
        )
    block.get_parameter_by_name('text').value = 'def'
    block.get_parameter_by_name('cmd').value = 'cat ${input[in]} | grep ${param[text]} > ${output[out]}'

    command = Command(block)

    command.run()
    print(command.block.outputs)
