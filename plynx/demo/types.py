import math
import plynx.node


def print_any(foo):
    print(str(type(foo)).replace("<", "").replace(">", ""))
    print(foo)


@plynx.node.output(name='int', var_type=int)
@plynx.node.output(name='str', var_type=str)
@plynx.node.output(name='dict', var_type=dict)
@plynx.node.output(name='float', var_type=float)
@plynx.node.output(name='bool', var_type=bool)
@plynx.node.operation(
    title="Produce Values",
    description="Echo all types",
)
def all_types():
    return {
        "int": 42,
        "str": "Hello world",
        "dict": {"foo": "woo"},
        "float": math.pi,
        "bool": True,
    }


@plynx.node.input(name='foo', var_type=int)
@plynx.node.operation(
    title="Print Int value",
)
def print_int(foo):
    print_any(foo)


@plynx.node.input(name='foo', var_type=str)
@plynx.node.operation(
    title="Print String value",
)
def print_str(foo):
    print_any(foo)


@plynx.node.input(name='foo', var_type=dict)
@plynx.node.operation(
    title="Print Dict value",
)
def print_dict(foo):
    print_any(foo)


@plynx.node.input(name='foo', var_type=float)
@plynx.node.operation(
    title="Print Float value",
)
def print_float(foo):
    print_any(foo)


@plynx.node.input(name='foo', var_type=bool)
@plynx.node.operation(
    title="Print Bool value",
)
def print_bool(foo):
    print_any(foo)


GROUP = plynx.node.utils.Group(
    title="Test Python built-in types",
    items=[
        all_types,
        print_int,
        print_str,
        print_dict,
        print_float,
        print_bool,
    ]
)
