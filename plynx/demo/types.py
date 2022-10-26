"""PLynx Operations defined as python code. Produce basic types."""
import math

import plynx.node


def print_any(value):
    """Format string to be html-friendly and print it."""
    print(str(type(value)).replace("<", "").replace(">", ""))
    print(value)


@plynx.node.output(name='int', var_type=int)
@plynx.node.output(name='str', var_type=str)
@plynx.node.output(name='dict', var_type=dict)
@plynx.node.output(name='float', var_type=float)
@plynx.node.output(name='bool', var_type=bool)
@plynx.node.operation(
    title="All types",
    description="Echo all types",
)
def all_types():
    """Make basic values for each type."""
    return {
        "int": 42,
        "str": "Hello world",
        "dict": {"foo": "woo"},
        "float": math.pi,
        "bool": True,
    }


@plynx.node.input(name='value', var_type=int)
@plynx.node.operation(
    title="Print Int value",
)
def print_int(value):
    """Print input value."""
    print_any(value)


@plynx.node.input(name='value', var_type=str)
@plynx.node.operation(
    title="Print String value",
)
def print_str(value):
    """Print input value."""
    print_any(value)


@plynx.node.input(name='value', var_type=dict)
@plynx.node.operation(
    title="Print Dict value",
)
def print_dict(value):
    """Print input value."""
    print_any(value)


@plynx.node.input(name='value', var_type=float)
@plynx.node.operation(
    title="Print Float value",
)
def print_float(value):
    """Print input value."""
    print_any(value)


@plynx.node.input(name='value', var_type=bool)
@plynx.node.operation(
    title="Print Bool value",
)
def print_bool(value):
    """Print input value."""
    print_any(value)


@plynx.node.input(name='value', var_type="py-json-file")
@plynx.node.output(name='value', var_type=dict)
@plynx.node.operation(
    title="File to Dict",
)
def file_to_dict(value):
    """Transform file object to dict"""
    return {
        "value": value,
    }


@plynx.node.input(name='value', var_type=dict)
@plynx.node.output(name='value', var_type="py-json-file")
@plynx.node.operation(
    title="Dict to File",
)
def dict_to_file(value):
    """transform dict to file object"""
    return {
        "value": value,
    }


GROUP = plynx.node.utils.Group(
    title="Test Python built-in types",
    items=[
        all_types,
        print_int,
        print_str,
        print_dict,
        print_float,
        print_bool,
        file_to_dict,
        dict_to_file,
    ]
)
