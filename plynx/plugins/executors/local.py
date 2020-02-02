from subprocess import Popen
import os
import signal
import logging
import pwd
import threading
import jinja2
from past.builtins import basestring
from collections import defaultdict
from plynx.constants import JobReturnStatus, NodeStatus, ParameterTypes
from plynx.db.node import Node, Parameter, Output
from plynx.utils.file_handler import get_file_stream, upload_file_stream
from plynx.utils.config import get_worker_config
import plynx.plugins.managers as plugin_magagers
from plynx.plugins.resources.common import File as FileCls
from plynx.plugins.executors import BaseExecutor
from plynx.constants import NodeResources

WORKER_CONFIG = get_worker_config()
_RESOURCE_MERGER_FUNC = lambda: defaultdict(list)


class ResourceMerger(object):
    def __init__(self, mandatory_keys=None):
        self._dict = defaultdict(_RESOURCE_MERGER_FUNC)
        mandatory_keys = mandatory_keys or []
        for key in mandatory_keys:
            self._dict[key] = _RESOURCE_MERGER_FUNC()

    def append(self, resource_dict, resource_name, is_list):
        for key, value in resource_dict.items():
            if is_list:
                self._dict[key][resource_name].append(value)
            else:
                self._dict[key][resource_name] = value

    def get_dict(self):
        """
        Return original dict.

        .. highlight:: python
        .. code-block:: python
        .. {
        ..     'inputs': {
        ..         'input_name_0': [],
        ..         'input_name_1': ['/tmp/1', '/tmp/2'],
        ..         'input_name_2': '/tmp/3',
        ..     },
        ..     'cloud_inputs': {
        ..         'input_name_0': [],
        ..         'input_name_1': ['gs://1', 'gs://2'],
        ..         'input_name_2': 'gs://3',
        ..     }
        .. }
        ..

        Out:    Dict
        """
        return self._dict


class BaseBash(BaseExecutor):
    logs_lock = threading.Lock()

    def __init__(self, node=None):
        super(BaseBash, self).__init__(node)
        self.sp = None
        self.logs_sizes = {}
        self.final_logs_uploaded = False
        self.logs = {}

    def exec_script(self, script_location, command='bash'):
        res = JobReturnStatus.SUCCESS

        try:
            pw_record = None
            if WORKER_CONFIG.user:
                pw_record = pwd.getpwnam(WORKER_CONFIG.user)

            def pre_exec():
                if WORKER_CONFIG.user:
                    user_uid = pw_record.pw_uid
                    user_gid = pw_record.pw_gid
                    os.setgid(user_gid)
                    os.setuid(user_uid)
                # Restore default signal disposition and invoke setsid
                for sig in ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ'):
                    if hasattr(signal, sig):
                        signal.signal(getattr(signal, sig), signal.SIG_DFL)
                os.setsid()

            env = os.environ.copy()

            # append running script to worker log
            with open(script_location, 'r') as sf, open(self.logs['worker'], 'a') as wf:
                wf.write(self._make_debug_text("Running script:"))
                wf.write(sf.read())
                wf.write('\n')
                wf.write(self._make_debug_text("End script"))

            with open(self.logs['stdout'], 'wb') as stdout_file, open(self.logs['stderr'], 'wb') as stderr_file:
                self.sp = Popen(
                    [command, script_location],
                    stdout=stdout_file, stderr=stderr_file,
                    cwd=self.workdir, env=env,
                    preexec_fn=pre_exec)

                self.sp.wait()

            if self.sp.returncode:
                raise Exception("Process returned non-zero value")

        except Exception as e:
            res = JobReturnStatus.FAILED
            logging.exception("Job failed")
            with open(self.logs['worker'], 'a+') as worker_log_file:
                worker_log_file.write(self._make_debug_text("JOB FAILED"))
                worker_log_file.write(str(e))

        return res

    def kill(self):
        if hasattr(self, 'sp') and self.sp:
            logging.info('Sending SIGTERM signal to bash process group')
            try:
                os.killpg(os.getpgid(self.sp.pid), signal.SIGTERM)
                logging.info('Killed {}'.format(self.sp.pid))
            except OSError as e:
                logging.error('Error: {}'.format(e))

    # Hack: do not pickle file
    def __getstate__(self):
        d = dict(self.__dict__)
        if 'sp' in d:
            del d['sp']
        return d

    @staticmethod
    def _make_debug_text(text):
        content = '\n'.join(['# {}'.format(line) for line in text.split('\n')])
        return "{border}\n{content}\n{border}\n".format(
            border='#' * 40,
            content=content
        )

    @classmethod
    def get_default_node(cls):
        node = Node()
        node.parameters = [
            Parameter.from_dict({
                'name': '_cmd',
                'parameter_type': ParameterTypes.CODE,
                'value': {
                    'mode': 'sh',
                    'value': 'set -e\n\n',
                },
                'mutable_type': False,
                'publicable': False,
                'removable': False,
                }
            ),
            Parameter.from_dict({
                'name': '_cacheable',
                'parameter_type': ParameterTypes.BOOL,
                'value': True,
                'mutable_type': False,
                'publicable': False,
                'removable': False,
            }),
            Parameter.from_dict({
                'name': '_timeout',
                'parameter_type': ParameterTypes.INT,
                'value': 600,
                'mutable_type': False,
                'publicable': True,
                'removable': False
            }),
        ]
        node.logs = [
            Output.from_dict({
                'name': 'stderr',
                'file_type': FileCls.NAME,
                'resource_id': None,
            }),
            Output({
                'name': 'stdout',
                'file_type': FileCls.NAME,
                'resource_id': None,
            }),
            Output({
                'name': 'worker',
                'file_type': FileCls.NAME,
                'resource_id': None,
            }),
        ]
        return node

    def _prepare_inputs(self, preview=False):
        resource_merger = ResourceMerger([NodeResources.INPUT])
        for input in self.node.inputs:
            is_list = not (input.min_count == 1 and input.max_count == 1)
            if preview:
                for i, value in enumerate(range(input.min_count)):
                    filename = os.path.join(self.workdir, 'i_{}_{}'.format(i, input.name))
                    resource_merger.append(
                        plugin_magagers.resource_manager[input.file_types[0]].prepare_input(filename, preview),
                        input.name,
                        is_list,
                    )
            else:
                for i, value in enumerate(input.values):
                    filename = os.path.join(self.workdir, 'i_{}_{}'.format(i, input.name))
                    with open(filename, 'wb') as f:
                        f.write(get_file_stream(value.resource_id).read())
                    resource_merger.append(
                        plugin_magagers.resource_manager[input.file_types[0]].prepare_input(filename, preview),
                        input.name,
                        is_list
                    )
        return resource_merger.get_dict()

    def _prepare_outputs(self, preview=False):
        resource_merger = ResourceMerger([NodeResources.OUTPUT])
        for output in self.node.outputs:
            filename = os.path.join(self.workdir, 'o_{}'.format(output.name))
            resource_merger.append(
                plugin_magagers.resource_manager[output.file_type].prepare_output(filename, preview),
                output.name,
                is_list=False
            )
        return resource_merger.get_dict()

    def _prepare_logs(self):
        with BaseBash.logs_lock:
            self.logs = {}
            for log in self.node.logs:
                filename = os.path.join(self.workdir, 'l_{}'.format(log.name))
                self.logs[log.name] = filename
                self.logs_sizes[log.name] = 0
            return self.logs

    def _get_script_fname(self, extension='.sh'):
        return os.path.join(self.workdir, "exec{}".format(extension))

    def _prepare_parameters(self):
        res = {}
        for parameter in self.node.parameters:
            value = None
            if parameter.parameter_type == ParameterTypes.ENUM:
                index = max(0, min(len(parameter.value.values) - 1, parameter.value.index))
                value = parameter.value.values[index]
            elif parameter.parameter_type in [ParameterTypes.LIST_STR, ParameterTypes.LIST_INT]:
                if parameter.parameter_type == ParameterTypes.LIST_INT:
                    value = list(map(int, parameter.value))
                else:
                    value = parameter.value
            elif parameter.parameter_type == ParameterTypes.CODE:
                value = parameter.value.value
            elif parameter.parameter_type == ParameterTypes.INT:
                value = int(parameter.value)
            else:
                value = parameter.value
            res[parameter.name] = value
        return res

    def _postprocess_outputs(self, outputs):
        for key, filename in outputs.items():
            if os.path.exists(filename):
                matching_outputs = list(filter(lambda o: o.name == key, self.node.outputs))
                assert len(matching_outputs) == 1, "Found more that 1 output with the same name `{}`".format(key)
                filename = plugin_magagers.resource_manager[matching_outputs[0].file_type].postprocess_output(filename)
                with open(filename, 'rb') as f:
                    self.node.get_output_by_name(key).resource_id = upload_file_stream(f)
            else:
                raise IOError("Output `{}` (filename: `{}`) does not exist".format(key, filename))

    def _postprocess_logs(self):
        self.upload_logs(final=True)

    def _extract_cmd_text(self):
        parameter = self.node.get_parameter_by_name('_cmd')
        if parameter.parameter_type == ParameterTypes.CODE:
            return parameter.value.value
        elif parameter.parameter_type == ParameterTypes.TEXT:
            # backward compatibility: `cmd` used to have type of TEXT
            return parameter.value
        raise TypeError("Process returned non-zero value")

    def upload_logs(self, final=False):
        with BaseBash.logs_lock:
            if self.final_logs_uploaded:
                return
            self.final_logs_uploaded = final
            for key, filename in self.logs.items():
                if key not in self.logs_sizes:
                    # the logs have not been initialized yey
                    continue
                if os.path.exists(filename) and os.stat(filename).st_size != self.logs_sizes[key]:
                    log = self.node.get_log_by_name(key)
                    self.logs_sizes[key] = os.stat(filename).st_size
                    with open(filename, 'rb') as f:
                        # resource_id should be None if the file has not been uploaded yet
                        # otherwise assign it
                        log.resource_id = upload_file_stream(f, log.resource_id)


class BashJinja2(BaseBash):
    HELP_TEMPLATE = '''# Use templates: {}
    # For example `{{{{ '{{{{' }}}} param['_timeout'] {{{{ '}}}}' }}}}` or `{{{{ '{{{{' }}}} input['abc'] {{{{ '}}}}' }}}}`

    '''
    ALIAS = 'BashJinja2'

    def __init__(self, node=None):
        super(BashJinja2, self).__init__(node)

    def run(self, preview=False):
        inputs = self._prepare_inputs(preview)
        parameters = self._prepare_parameters()
        outputs = self._prepare_outputs(preview)
        logs = self._prepare_logs()
        if preview:
            help = BashJinja2.HELP_TEMPLATE.format(list(inputs.keys()) + list(outputs.keys()) + [NodeResources.PARAM])
        else:
            help = ''
        cmd = '{help}{cmd}'.format(
            help=help,
            cmd=self._extract_cmd_text()
        )
        cmd_template = jinja2.Template(cmd)
        resources = inputs
        resources.update(outputs)
        cmd_string = cmd_template.render(
            param=parameters,
            log=logs,
            **resources
        )
        if preview:
            return cmd_string

        script_location = self._get_script_fname()
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_string
            )

        res = self.exec_script(script_location)

        self._postprocess_outputs(outputs[NodeResources.OUTPUT])
        self._postprocess_logs()

        return res

    def status(self):
        pass

    @classmethod
    def get_default_node(cls):
        node = super().get_default_node()
        node.title = 'New'
        return node


class PythonNode(BaseBash):
    ALIAS = 'PythonNode'

    def __init__(self, node=None):
        super(PythonNode, self).__init__(node)

    def run(self, preview=False):
        inputs = self._prepare_inputs(preview)
        parameters = self._prepare_parameters()
        outputs = self._prepare_outputs(preview)
        logs = self._prepare_logs()
        cmd = self._extract_cmd_text()
        cmd_array = []
        cmd_array.extend([
            self._get_arguments_string(key, value)
            for key, value in inputs.items()
        ])
        cmd_array.extend([
            self._get_arguments_string(key, value)
            for key, value in outputs.items()
        ])
        cmd_array.extend([
            self._get_arguments_string(NodeResources.PARAM, parameters),
            self._get_arguments_string(NodeResources.LOG, logs),
            "\n",
            "# User code starts there:",
            cmd,
        ])
        cmd_string = '\n'.join(cmd_array)

        if preview:
            return cmd_string

        script_location = self._get_script_fname(extension='.py')
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_string
            )

        res = self.exec_script(script_location, command='python')

        self._postprocess_outputs(outputs[NodeResources.OUTPUT])
        self._postprocess_logs()

        return res

    def status(self):
        pass

    @classmethod
    def _get_arguments_string(cls, var_name, arguments):
        res = ['{} = {{}}'.format(var_name)]
        for key, value in arguments.items():
            res.append('{var_name}["{key}"] = {value}'.format(
                var_name=var_name,
                key=key,
                value=repr(cls._pythonize(value))
                )
            )
        return '\n'.join(res)

    @staticmethod
    def _pythonize(value):
        if isinstance(value, basestring):
            repr(value)
        return value

    @classmethod
    def get_default_node(cls):
        node = super().get_default_node()
        node.title = 'New'
        param = list(filter(lambda p: p.name == '_cmd', node.parameters))[0]
        param.value.mode = 'python'
        param.value.value = 'print("hello world")'
        return node
