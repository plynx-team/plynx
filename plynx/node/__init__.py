from dataclasses import dataclass, field
from typing import Any, List, Optional
import cloudpickle
import plynx.node.typing as typings

import plynx.node.utils as utils    # noqa


@dataclass
class InputItem:
    name: str
    file_type: str
    is_array: bool
    min_count: int

    def to_dict(self):
        return {
            "name": self.name,
            "file_type": self.file_type,
            "is_array": self.is_array,
            "min_count": self.min_count,
        }


@dataclass
class OutputItem:
    name: str
    file_type: str
    is_array: bool
    min_count: int

    def to_dict(self):
        return {
            "name": self.name,
            "file_type": self.file_type,
            "is_array": self.is_array,
            "min_count": self.min_count,
        }


@dataclass
class ParamItem:
    name: str
    parameter_type: str
    value: Any
    widget: Optional[str]

    def to_dict(self):
        return {
            "name": self.name,
            "parameter_type": self.parameter_type,
            "value": self.value,
            "widget": self.widget,
        }


@dataclass
class PlynxParams:
    title: str
    description: str
    kind: str
    node_type: str
    inputs: List[InputItem] = field(default_factory=list)
    params: List[ParamItem] = field(default_factory=list)
    outputs: List[OutputItem] = field(default_factory=list)


def input(
    name=None,
    var_type=None,
    is_array=False,
    min_count=1,
):
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
    def decorator(func_or_class):
        func_or_class.plynx_params.params.insert(0, ParamItem(
            name=name,
            parameter_type=typings.type_to_str(var_type),
            value=default,
            widget=None if widget is None else widget or name,
        ))
        return func_or_class
    return decorator


def operation(node_type=None, title=None, description="", kind=None):
    def decorator(func_or_class):
        func_or_class.plynx_params = PlynxParams(
            title=title or func_or_class.__name__,
            description=description,
            kind=kind or "python-code-operation",
            node_type=node_type or "python-code-operation",
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
