"""Standard Executors that support running on local machine."""
import logging
import os
import signal
import threading
from abc import abstractmethod
from collections import defaultdict
from subprocess import Popen
from typing import Any, Dict, List, Optional, Union

import jinja2
from past.builtins import basestring

import plynx.plugins.executors.bases
import plynx.utils.plugin_manager
from plynx.constants import NodeResources, NodeRunningStatus, ParameterTypes
from plynx.db.node import Node, Output, Parameter, ParameterCode
from plynx.plugins.resources.common import FILE_KIND
from plynx.utils.file_handler import get_file_stream, upload_file_stream


def _resource_merger_func():
    return defaultdict(list)


def prepare_parameters_for_python(parameters: List[Parameter]) -> Dict[str, Any]:
    """Pythonize parameters"""
    res = {}
    for parameter in parameters:
        value = None
        if parameter.parameter_type == ParameterTypes.ENUM:
            index = max(0, min(len(parameter.value.values) - 1, int(parameter.value.index)))
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
        elif parameter.parameter_type == ParameterTypes.FLOAT:
            value = float(parameter.value)
        else:
            value = parameter.value
        res[parameter.name] = value
    return res


class _ResourceMerger:
    # TODO rename arguments
    def __init__(self, init_level_0: List[str], init_level_1: List[str]):
        self._dict: Dict[str, Dict[str, Union[List[str], str]]] = defaultdict(_resource_merger_func)
        for key in init_level_0:
            self._dict[key] = _resource_merger_func()
            for lev_1 in init_level_1:
                self._dict[key][lev_1] = []

    def append(self, resource_dict: Dict[str, List[str]], resource_name: str, is_list: bool):
        """Append values to the resource"""
        for key, value in resource_dict.items():
            if is_list:
                self._dict[key][resource_name].append(value)    # type: ignore
            else:
                self._dict[key][resource_name] = value

    def get_dict(self) -> Dict[str, Dict[str, Union[List[str], str]]]:
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


class BaseBash(plynx.plugins.executors.bases.PLynxAsyncExecutorWithDirectory):
    """Base Executor that will use unix bash as a backend."""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, node: Optional[Node] = None):
        super().__init__(node)
        self.sp: Optional[Popen] = None
        self.logs_sizes: Dict[str, int] = {}
        self.final_logs_uploaded = False
        self.logs: Dict[str, str] = {}
        self.logs_lock = threading.Lock()
        self.output_to_filename: Dict[str, str] = {}
        self._resource_manager = plynx.utils.plugin_manager.get_resource_manager()
        self._command = 'bash'
        self._node_running_status = NodeRunningStatus.READY

    def exec_script(self, script_location: str) -> str:
        """Execute the script when inputs are initialized."""
        self._node_running_status = NodeRunningStatus.SUCCESS

        try:
            def pre_exec():
                # Restore default signal disposition and invoke setsid
                for sig in ('SIGPIPE', 'SIGXFZ', 'SIGXFSZ'):
                    if hasattr(signal, sig):
                        signal.signal(getattr(signal, sig), signal.SIG_DFL)
                os.setsid()

            env = os.environ.copy()

            # append running script to worker log
            with open(script_location, 'r') as script_f, open(self.logs['worker'], 'a') as worker_f:
                worker_f.write(self._make_debug_text("Running script:"))
                worker_f.write(script_f.read())
                worker_f.write('\n')
                worker_f.write(self._make_debug_text("End script"))

            with open(self.logs['stdout'], 'wb') as stdout_file, open(self.logs['stderr'], 'wb') as stderr_file:
                self.sp = Popen(    # pylint: disable=subprocess-popen-preexec-fn,consider-using-with
                    [self._command, script_location],
                    stdout=stdout_file, stderr=stderr_file,
                    cwd=self.workdir, env=env,
                    preexec_fn=pre_exec)

                assert self.sp, "Popen object was not initialized"
                self.sp.wait()

            if self.sp.returncode:
                raise Exception("Process returned non-zero value")

        except Exception as e:  # pylint: disable=broad-except
            if self._node_running_status != NodeRunningStatus.CANCELED:
                self._node_running_status = NodeRunningStatus.FAILED
            logging.exception("Job failed")
            with open(self.logs['worker'], 'a+') as worker_log_file:
                worker_log_file.write(self._make_debug_text("JOB FAILED"))
                worker_log_file.write(str(e))

        return self._node_running_status

    def kill(self):
        if not hasattr(self, 'sp') or not self.sp:
            return

        self._node_running_status = NodeRunningStatus.CANCELED

        logging.info('Sending SIGTERM signal to bash process group')
        try:
            os.killpg(os.getpgid(self.sp.pid), signal.SIGTERM)
            logging.info(f"Killed %d{self.sp.pid}")
        except OSError as e:
            logging.error(f"Error: {e}")

    def is_updated(self):
        logging.info('Tick')
        return self.upload_logs(final=False)

    # Hack: do not pickle file
    def __getstate__(self):
        logging.critical('Run into `__getstate__`! Look ad `logs_lock` variable')
        dict_copy = dict(self.__dict__)
        if 'sp' in dict_copy:
            del dict_copy['sp']
        return dict_copy

    @staticmethod
    def _make_debug_text(text: str) -> str:
        content = "\n".join([f"# {line}" for line in text.split("\n")])
        border = "#" * 40
        return f"{border}\n{content}\n{border}\n"

    @classmethod
    def get_default_node(cls, is_workflow: bool) -> Node:
        if is_workflow:
            raise Exception('This class cannot be a workflow')
        node = super().get_default_node(is_workflow)
        node.parameters.extend(
            [
                Parameter(
                    name='_cmd',
                    parameter_type=ParameterTypes.CODE,
                    value=ParameterCode(
                        mode='sh',
                        value='set -e\n\necho "hello world"\n',
                    ),
                    mutable_type=False,
                    publicable=False,
                    removable=False,
                ),
                Parameter(
                    name='_cacheable',
                    parameter_type=ParameterTypes.BOOL,
                    value=False,
                    mutable_type=False,
                    publicable=False,
                    removable=False,
                ),
                Parameter(
                    name='_timeout',
                    parameter_type=ParameterTypes.INT,
                    value=600,
                    mutable_type=False,
                    publicable=True,
                    removable=False
                ),
            ]
        )
        node.logs.extend(
            [
                Output(
                    name='stderr',
                    file_type=FILE_KIND,
                ),
                Output(
                    name='stdout',
                    file_type=FILE_KIND,
                ),
                Output(
                    name='worker',
                    file_type=FILE_KIND,
                ),
            ]
        )
        return node

    def _prepare_inputs(self, preview: bool = False):
        assert self.node, "Attribute `node` is undefined"
        resource_merger = _ResourceMerger(
            [NodeResources.INPUT],
            [input.name for input in self.node.inputs if input.is_array],
        )
        for input in self.node.inputs:  # pylint: disable=redefined-builtin
            if preview:
                for i, _ in enumerate(range(input.min_count)):
                    filename = os.path.join(self.workdir, f"i_{i}_{input.name}")
                    resource_merger.append(
                        self._resource_manager.kind_to_resource_class[input.file_type].prepare_input(filename, preview),
                        input.name,
                        input.is_array,
                    )
            else:
                for i, value in enumerate(input.values):
                    filename = os.path.join(self.workdir, f"i_{i}_{input.name}")
                    with open(filename, 'wb') as f:
                        f.write(get_file_stream(value).read())
                    resource_merger.append(
                        self._resource_manager.kind_to_resource_class[input.file_type].prepare_input(filename, preview),
                        input.name,
                        input.is_array,
                    )
        return resource_merger.get_dict()

    def _prepare_outputs(self, preview: bool = False):
        assert self.node, "Attribute `node` is undefined"
        resource_merger = _ResourceMerger(
            [NodeResources.OUTPUT],
            [output.name for output in self.node.outputs if output.is_array],
        )
        for output in self.node.outputs:
            filename = os.path.join(self.workdir, f"o_{output.name}")
            self.output_to_filename[output.name] = filename
            resource_merger.append(
                self._resource_manager.kind_to_resource_class[output.file_type].prepare_output(filename, preview),
                output.name,
                is_list=False
            )
        return resource_merger.get_dict()

    def _prepare_logs(self):
        with self.logs_lock:
            self.logs = {}
            for log in self.node.logs:
                filename = os.path.join(self.workdir, f"l_{log.name}")
                self.logs[log.name] = filename
                self.logs_sizes[log.name] = 0
            return self.logs

    def _get_script_fname(self, extension: str = ".sh"):
        return os.path.join(self.workdir, f"exec{extension}")

    def _prepare_parameters(self):
        return prepare_parameters_for_python(self.node.parameters)

    def _postprocess_outputs(self, outputs: Dict[str, str]):
        assert self.node, "Attribute `node` is undefined"
        for key, filename in outputs.items():
            logging.info(f"Uploading output `{key}` - `{filename}`")
            if os.path.exists(filename):
                logging.info('path exists')
                matching_outputs = list(filter(lambda o: o.name == key, self.node.outputs))     # pylint: disable=cell-var-from-loop
                assert len(matching_outputs) == 1, f"Found more that 1 output with the same name `{key}`"
                filename = self._resource_manager.kind_to_resource_class[matching_outputs[0].file_type].postprocess_output(filename)
                logging.info(filename)
                with open(filename, 'rb') as f:
                    # resource_id
                    self.node.get_output_by_name(key).values = [upload_file_stream(f)]
                    logging.info(self.node.get_output_by_name(key).to_dict())
            else:
                raise IOError(f"Output `{key}` (filename: `{filename}`) does not exist")

    def _postprocess_logs(self) -> None:
        self.upload_logs(final=True)

    def _extract_cmd_text(self) -> str:
        assert self.node, "Attribute `node` is undefined"
        parameter = self.node.get_parameter_by_name('_cmd')
        if parameter.parameter_type == ParameterTypes.CODE:
            return parameter.value.value
        elif parameter.parameter_type == ParameterTypes.TEXT:
            # backward compatibility: `cmd` used to have type of TEXT
            return parameter.value
        raise TypeError("Process returned non-zero value")

    def upload_logs(self, final: bool = False) -> bool:
        """Upload logs to the storage. When Final is False, only upload on update"""
        assert self.node, "Attribute `node` is undefined"
        is_dirty = False
        with self.logs_lock:
            if self.final_logs_uploaded:
                return is_dirty
            self.final_logs_uploaded = final
            for key, filename in self.logs.items():
                if key not in self.logs_sizes:
                    # the logs have not been initialized yet
                    continue
                if os.path.exists(filename) and os.stat(filename).st_size != self.logs_sizes[key]:
                    is_dirty = True
                    log = self.node.get_log_by_name(key)
                    self.logs_sizes[key] = os.stat(filename).st_size
                    with open(filename, 'rb') as f:
                        # resource_id should be None if the file has not been uploaded yet
                        # otherwise assign it
                        log.values = [upload_file_stream(f, log.values[0] if len(log.values) > 0 else None)]
        return is_dirty

    @abstractmethod
    def run(self, preview=False):
        pass


class BashJinja2(BaseBash):
    """Local executor that uses jinja2 template to format a bash script."""
    HELP_TEMPLATE = """# Use templates: {}
# For example `{{{{ '{{{{' }}}} params['_timeout'] {{{{ '}}}}' }}}}` or `{{{{ '{{{{' }}}} inputs['abc'] {{{{ '}}}}' }}}}`

"""

    def run(self, preview: bool = False) -> str:
        inputs = self._prepare_inputs(preview)
        parameters = self._prepare_parameters()
        outputs = self._prepare_outputs(preview)
        logs = self._prepare_logs()
        if preview:
            help_msg = BashJinja2.HELP_TEMPLATE.format(list(inputs.keys()) + list(outputs.keys()) + [NodeResources.PARAM])
        else:
            help_msg = ""
        cmd = f"{help_msg}{self._extract_cmd_text()}"
        cmd_template = jinja2.Template(cmd)
        resources = inputs
        resources.update(outputs)
        cmd_string = cmd_template.render(
            params=parameters,
            logs=logs,
            **resources
        )
        if preview:
            return cmd_string

        script_location = self._get_script_fname()
        with open(script_location, 'w') as script_file:
            script_file.write(
                cmd_string
            )

        self._node_running_status = self.exec_script(script_location)

        self._postprocess_outputs(outputs[NodeResources.OUTPUT])
        self._postprocess_logs()

        return self._node_running_status

    @classmethod
    def get_default_node(cls, is_workflow: bool) -> Node:
        node = super().get_default_node(is_workflow)
        node.title = 'New bash script'
        return node


class PythonNode(BaseBash):
    """Local executor that uses python template to format a bash script."""
    def __init__(self, node: Optional[Node] = None):
        super().__init__(node)
        self._command = 'python'

    def run(self, preview: bool = False) -> str:
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

        res = self.exec_script(script_location)

        self._postprocess_outputs(outputs[NodeResources.OUTPUT])
        self._postprocess_logs()

        return res

    @classmethod
    def _get_arguments_string(cls, var_name: str, arguments: Dict[str, Any]) -> str:
        res = [f"{var_name} = {{}}"]
        for key, value in arguments.items():
            value = repr(cls._pythonize(value))
            res.append(f'{var_name}["{key}"] = {value}')
        return '\n'.join(res)

    @staticmethod
    def _pythonize(value: Any) -> Any:
        if isinstance(value, basestring):
            repr(value)
        return value

    @classmethod
    def get_default_node(cls, is_workflow: bool) -> Node:
        node = super().get_default_node(is_workflow)
        node.title = 'New python script'
        param = list(filter(lambda p: p.name == '_cmd', node.parameters))[0]
        param.value.mode = 'python'
        param.value.value = 'print("hello world")'
        return node


class File(plynx.plugins.executors.bases.PLynxAsyncExecutor):
    """Dummy executor that represents STATIC Operations."""

    def run(self, preview: bool = False):
        if preview:
            return "Cannot preview the content. Please check the outputs."
        raise NotImplementedError()

    def kill(self):
        raise NotImplementedError()

    @classmethod
    def get_default_node(cls, is_workflow: bool) -> Node:
        raise NotImplementedError()
