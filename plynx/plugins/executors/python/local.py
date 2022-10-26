"""Python Operation"""
import contextlib
import inspect
import os
import sys
import threading
import uuid
from typing import Any, Callable, Dict

import cloudpickle

import plynx.plugins.executors.bases
import plynx.plugins.executors.local
import plynx.utils.plugin_manager
from plynx.constants import NodeRunningStatus, ParameterTypes
from plynx.db.node import Input, Node, Output, Parameter, ParameterCode

DEFAULT_CMD = """# Python Operation
# The code of the operation have to be defined as a function
#
# A function must be named `operation`.
# The arguments are named and must represent then inputs of the PLynx Operation.
# The function must return a dictionary that map to the outputs of PLynx Operation
def operation(int_a, int_b):
    return {"sum": int_a + int_b}
"""

stateful_init_mutex = threading.Lock()
stateful_class_registry = {}

_resource_manager = plynx.utils.plugin_manager.get_resource_manager()


def materialize_fn_or_cls(node: Node) -> Callable:
    """Unpickle the function"""

    pickled_fn_parameter = node.get_parameter_by_name("_pickled_fn", throw=False)
    code_parameter = node.get_parameter_by_name("_cmd", throw=False)
    assert not (pickled_fn_parameter and code_parameter), "`_pickled_fn` and `_cmd` cannot be both non-null"
    if pickled_fn_parameter:
        fn_str: str = pickled_fn_parameter.value

        func_bytes = bytes.fromhex(fn_str)
        func = cloudpickle.loads(func_bytes)
        return func
    elif code_parameter:
        code = code_parameter.value.value
        local_vars: Dict[str, Any] = {}
        exec(code, globals(), local_vars)   # pylint: disable=W0122
        return local_vars["operation"]
    raise ValueError("No function to materialize")


def assign_outputs(node: Node, output_dict: Dict[str, Any]):
    """Apply output_dict to node's outputs."""
    if not output_dict:
        return
    for key, value in output_dict.items():
        node_output = node.get_output_by_name(key)
        func = _resource_manager.kind_to_resource_class[node_output.file_type].postprocess_output
        if node_output.is_array:
            node_output.values = list(map(func, value))
        else:
            node_output.values = [func(value)]


class redirect_to_plynx_logs:   # pylint: disable=invalid-name
    """Redirect stdout and stderr to standard PLynx Outputs"""
    # pylint: disable=too-many-instance-attributes

    def __init__(self, node: Node, stdout: str, stderr: str):
        self.stdout_filename = str(uuid.uuid4())
        self.stderr_filename = str(uuid.uuid4())

        self.stdout = stdout
        self.stderr = stderr

        self.node = node

        self.names_map = [
            (self.stdout_filename, self.stdout),
            (self.stderr_filename, self.stderr),
        ]

        self.stdout_file = None
        self.stderr_file = None

        self.stdout_redirect = None
        self.stderr_redirect = None

    def __enter__(self):
        self.stdout_file = open(self.stdout_filename, 'w')
        self.stderr_file = open(self.stderr_filename, 'w')

        self.stdout_redirect = contextlib.redirect_stdout(self.stdout_file)
        self.stderr_redirect = contextlib.redirect_stderr(self.stderr_file)

        self.stdout_redirect.__enter__()
        self.stderr_redirect.__enter__()

    def __exit__(self, *args):

        self.stdout_redirect.__exit__(*sys.exc_info())
        self.stderr_redirect.__exit__(*sys.exc_info())

        self.stdout_file.close()
        self.stderr_file.close()

        for filename, logs_name in self.names_map:
            if os.stat(filename).st_size > 0:
                with plynx.utils.file_handler.open(filename, "w") as f:
                    with open(filename) as fi:
                        f.write(fi.read())
                output = self.node.get_log_by_name(name=logs_name)
                output.values = [filename]


def prep_args(node: Node) -> Dict[str, Any]:
    """Pythonize inputs and parameters"""
    args = {}
    for input in node.inputs:   # pylint: disable=redefined-builtin
        func = _resource_manager.kind_to_resource_class[input.file_type].preprocess_input
        if input.is_array:
            args[input.name] = list(map(func, input.values))
        else:
            args[input.name] = func(input.values[0])

    # TODO smater way to determine what parameters to pass
    visible_parameters = list(filter(lambda param: param.widget is not None, node.parameters))
    args.update(
        plynx.plugins.executors.local.prepare_parameters_for_python(visible_parameters)
    )
    return args


class PythonNode(plynx.plugins.executors.bases.PLynxSyncExecutor):
    """
    Class is used as a placeholder for local python executor
    """

    def run(self, preview: bool = False) -> str:
        assert self.node, "Executor memeber `node` is not defined"
        func = materialize_fn_or_cls(self.node)
        if inspect.isclass(func):
            with stateful_init_mutex:
                if self.node.code_hash not in stateful_class_registry:
                    with redirect_to_plynx_logs(self.node, "init_stdout", "init_stderr"):
                        stateful_class_registry[self.node.code_hash] = func()
                func = stateful_class_registry[self.node.code_hash]

        with redirect_to_plynx_logs(self.node, "stdout", "stderr"):
            res = func(**prep_args(self.node))

        assign_outputs(self.node, res)

        return NodeRunningStatus.SUCCESS

    def kill(self):
        raise NotImplementedError()

    @classmethod
    def get_default_node(cls, is_workflow: bool) -> Node:
        """Generate a new default Node for this executor"""
        if is_workflow:
            raise Exception('This class cannot be a workflow')
        node = super().get_default_node(is_workflow)
        node.inputs.extend(
            [
                Input(
                    name="int_a",
                    file_type="int",
                ),
                Input(
                    name="int_b",
                    file_type="int",
                ),
            ]
        )
        node.outputs.extend(
            [
                Output(
                    name="sum",
                    file_type="int",
                ),
            ]
        )
        node.parameters.extend(
            [
                Parameter(
                    name="_cmd",
                    parameter_type=ParameterTypes.CODE,
                    value=ParameterCode(
                        mode="python",
                        value=DEFAULT_CMD,
                    ),
                    mutable_type=False,
                    publicable=False,
                    removable=False,
                ),
            ]
        )
        return node
