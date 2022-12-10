"""
PLynx API for generation user Nodes.
"""
# pylint: disable=consider-using-from-import
from dataclasses import dataclass, field
from typing import Any, List, Optional

import cloudpickle

import plynx.node.typing as typings
import plynx.node.utils as utils  # noqa


@dataclass
class InputItem:
    """Input item abstraction"""
    name: str
    file_type: str
    is_array: bool
    min_count: int

    def to_dict(self):
        """Dict representation"""
        return {
            "name": self.name,
            "file_type": self.file_type,
            "is_array": self.is_array,
            "min_count": self.min_count,
        }


@dataclass
class OutputItem:
    """Output item abstraction"""
    name: str
    file_type: str
    is_array: bool
    min_count: int

    def to_dict(self):
        """Dict representation"""
        return {
            "name": self.name,
            "file_type": self.file_type,
            "is_array": self.is_array,
            "min_count": self.min_count,
        }


@dataclass
class ParamItem:
    """Parameter item abstraction"""
    name: str
    parameter_type: str
    value: Any
    widget: Optional[str]

    def to_dict(self):
        """Dict representation"""
        return {
            "name": self.name,
            "parameter_type": self.parameter_type,
            "value": self.value,
            "widget": self.widget,
        }


@dataclass
class PlynxParams:
    """Internal PLynx Node params"""
    # pylint: disable=too-many-instance-attributes
    title: str
    description: str
    kind: str
    node_type: str
    auto_run_enabled: bool = True
    inputs: List[InputItem] = field(default_factory=list)
    params: List[ParamItem] = field(default_factory=list)
    outputs: List[OutputItem] = field(default_factory=list)


# pylint: disable=redefined-builtin
def input(
    name=None,
    var_type=None,
    is_array=False,
    min_count=1,
):
    """PLynx Operation Input"""
    def decorator(func_or_class):
        func_or_class.plynx_params.inputs.insert(0, InputItem(
            name=name,
            file_type=typings.type_to_str(var_type),
            is_array=is_array,
            min_count=min_count,
        ))
        return func_or_class
    return decorator


def output(
    name=None,
    var_type=None,
    is_array=False,
    min_count=1,
):
    """PLynx Operation Output"""
    def decorator(func_or_class):
        func_or_class.plynx_params.outputs.insert(0, OutputItem(
            name=name,
            file_type=typings.type_to_str(var_type),
            is_array=is_array,
            min_count=min_count,
        ))
        return func_or_class
    return decorator


def param(
    name=None,
    var_type=None,
    default=None,
    widget="",
):
    """PLynx Operation Parameter"""
    def decorator(func_or_class):
        func_or_class.plynx_params.params.insert(0, ParamItem(
            name=name,
            parameter_type=typings.type_to_str(var_type),
            value=default,
            widget=None if widget is None else widget or name,
        ))
        return func_or_class
    return decorator


def operation(node_type=None, title=None, description="", kind=None, auto_run_enabled: bool = True):
    """PLynx user-defined Operation"""
    def decorator(func_or_class):
        func_or_class.plynx_params = PlynxParams(
            title=title or func_or_class.__name__,
            description=description,
            kind=kind or "python-code-operation",
            node_type=node_type or "python-code-operation",
            auto_run_enabled=auto_run_enabled,
            inputs=[],
            params=[],
            outputs=[],
        )

        fn_dumped = cloudpickle.dumps(func_or_class).hex()
        func_or_class.plynx_params.params.append(ParamItem(
            name="_pickled_fn",
            parameter_type="str",
            value=fn_dumped,
            widget=None,
        ))
        return func_or_class
    return decorator


parameter = param   # Alias
