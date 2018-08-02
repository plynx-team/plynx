from subprocess import Popen, PIPE
import os
import shutil
import signal
import uuid
import logging
from constants import JobReturnStatus, NodeStatus, FileTypes, ParameterTypes
from db import Node, Output, Parameter
from utils.file_handler import get_file_stream, upload_file_stream


class BaseBash(object):
    def exec_script(self, script_location, logs):
        res = JobReturnStatus.SUCCESS

        try:
            def pre_exec():
                # Restore default signal disposition and invoke setsid
                for sig in ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ'):
                    if hasattr(signal, sig):
                        signal.signal(getattr(signal, sig), signal.SIG_DFL)
                os.setsid()

            env = os.environ.copy()
            shutil.copyfile(script_location, logs['worker'])
            sp = Popen(
                ['bash', script_location],
                stdout=PIPE, stderr=PIPE,
                cwd='/tmp', env=env,
                preexec_fn=pre_exec)

            line = ''
            with open(logs['stdout'], 'w') as f:
                for line in iter(sp.stdout.readline, b''):
                    f.write(line)
            with open(logs['stderr'], 'w') as f:
                for line in iter(sp.stderr.readline, b''):
                    f.write(line)
            sp.wait()

            if sp.returncode:
                raise Exception("Process returned non-zero value")

        except Exception as e:
            res = JobReturnStatus.FAILED
            logging.exception("Job failed")
            with open(logs['worker'], 'a+') as worker_log_file:
                worker_log_file.write('\n' * 3)
                worker_log_file.write('#' * 60 + '\n')
                worker_log_file.write('JOB FAILED\n')
                worker_log_file.write('#' * 60 + '\n')
                worker_log_file.write(str(e))

        return res

    @classmethod
    def get_default(cls):
        node = Node()
        node.title = ''
        node.description = ''
        node.base_node_name = cls.get_base_name()
        node.node_status = NodeStatus.CREATED
        node.public = False
        node.parameters = [
            Parameter(
                name='cmd',
                parameter_type=ParameterTypes.TEXT,
                value='bash -c " "',
                mutable_type=False,
                publicable=False,
                removable=False
                ),
            Parameter(
                name='cacheable',
                parameter_type=ParameterTypes.BOOL,
                value=True,
                mutable_type=False,
                publicable=False,
                removable=False
                )
            ]
        node.logs = [
            Output(
                name='stderr',
                file_type=FileTypes.FILE,
                resource_id=None
                ),
            Output(
                name='stdout',
                file_type=FileTypes.FILE,
                resource_id=None
                ),
            Output(
                name='worker',
                file_type=FileTypes.FILE,
                resource_id=None
                )
            ]
        return node

    @staticmethod
    def _prepare_inputs(inputs, preview):
        res = {}
        for input in inputs:
            filenames = []
            if preview:
                for i, value in enumerate(range(input.min_count)):
                    filename = os.path.join('/tmp', '{}_{}_{}'.format(str(uuid.uuid1()), i, input.name))
                    filenames.append(filename)
            else:
                for i, value in enumerate(input.values):
                    filename = os.path.join('/tmp', '{}_{}_{}'.format(str(uuid.uuid1()), i, input.name))
                    with open(filename, 'wb') as f:
                        f.write(get_file_stream(value.resource_id).read())
                    filenames.append(filename)
            res[input.name] = ' '.join(filenames)                                                       #!!!!!!
        return res

    @staticmethod
    def _prepare_outputs(outputs):
        res = {}
        for output in outputs:
            filename = os.path.join('/tmp', '{}_{}'.format(str(uuid.uuid1()), output.name))
            res[output.name] = filename
        return res

    @staticmethod
    def _prepare_logs(logs):
        res = {}
        for log in logs:
            filename = os.path.join('/tmp', '{}_{}'.format(str(uuid.uuid1()), log.name))
            res[log.name] = filename
        return res

    @staticmethod
    def _get_script_fname():
        return os.path.join('/tmp', '{}_{}'.format(str(uuid.uuid1()), "exec.sh"))

    @staticmethod
    def _prepare_parameters(parameters):
        res = {}
        for parameter in parameters:
            if parameter.parameter_type == ParameterTypes.ENUM:
                index = max(0, min(len(parameter.value.values) - 1, parameter.value.index))
                res[parameter.name] = parameter.value.values[index]
            elif parameter.parameter_type in [ParameterTypes.LIST_STR, ParameterTypes.LIST_INT]:
                res[parameter.name] = ' '.join(map(str, parameter.value))                               #!!!!!!!!!
            else:
                res[parameter.name] = parameter.value
        return res

    def _postprocess_outputs(self, outputs):
        for key, filename in outputs.iteritems():
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    self.node.get_output_by_name(key).resource_id = upload_file_stream(f)

    def _postprocess_logs(self, logs):
        for key, filename in logs.iteritems():
            if os.path.exists(filename) and os.stat(filename).st_size != 0:
                with open(filename, 'rb') as f:
                    self.node.get_log_by_name(key).resource_id = upload_file_stream(f)
