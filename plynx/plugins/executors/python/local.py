"""Python Operation"""
import plynx.base.executor
from plynx.constants import ParameterTypes
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


class PythonNode(plynx.base.executor.BaseExecutor):
    """
    Class is used as a placeholder for local python executor
    """

    def run(self, preview: bool = False) -> str:
        raise NotImplementedError()

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
