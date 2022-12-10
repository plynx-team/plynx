"""PLynx Operations defined as python code. Using slighty more advanced functions than printing variables."""
import math
import random
import sys
import time

import plynx.node


@plynx.node.param(name='value', var_type=int, default=1)
@plynx.node.output(name='x', var_type=int)
@plynx.node.operation(
    title="Make integer"
)
def make_int(value):
    """Pass Integer value as output."""
    return {
        "x": value,
    }


@plynx.node.input(name='x', var_type=int)
@plynx.node.input(name='y', var_type=int)
@plynx.node.output(name='res', var_type=str)
@plynx.node.param(name='coef', var_type=int, default=1)
@plynx.node.operation(
    title="Multiple inputs",
    description="x * coef + y * pi",
)
def example_func(x, y, coef):
    """Math expression"""
    print(f"x: {type(x)}")
    print(f"y: {type(y)}")
    print(f"coef {type(coef)}")
    res = x * coef + y * math.pi
    return {'res': str(res)}


@plynx.node.input(name='x', var_type=int, is_array=True, min_count=0)
@plynx.node.param(name='timeout', var_type=int, default=3)
@plynx.node.output(name='x', var_type=int)
@plynx.node.operation(
    title="Sleep",
    description="Sleep for timeout sec and add 1.",
)
def sleep(x, timeout):
    """Sleep for timeout sec and add 1."""
    print(f"Sleeping for {timeout} sec")
    time.sleep(timeout)
    return {
        "x": sum(x) + 1
    }


@plynx.node.input(name='x', var_type=int, is_array=True, min_count=0)
@plynx.node.output(name='x', var_type=int)
@plynx.node.operation(
    title="Raise exception",
    description="Always raise exception",
)
def error(x):
    """Always raise exception"""
    raise Exception("Expected exception")


@plynx.node.input(name='x', var_type=int, is_array=True, min_count=0)
@plynx.node.output(name='x', var_type=int)
@plynx.node.operation(
    title="Stateful sum",
    description="Add 1 and keep the previous value",
)
class Statefull:
    """Add 1 and keep the previous value"""
    def __init__(self):
        self.accum = 0
        self.random = random.random()
        print(f"Init worker with id {self.random}")

    def __call__(self, x):
        self.accum += sum(x) + 1
        print(f"I am {self.random} living on {id(self)}")
        print(f"x: {x}")
        print(f"self.accum: {self.accum}")
        print("I am error", file=sys.stderr)
        return {
            "x": self.accum
        }


@plynx.node.input(name='x', var_type=int, is_array=True, min_count=0)
@plynx.node.output(name='x', var_type=int)
@plynx.node.operation(
    title="Wait manual run",
    auto_run_enabled=False
)
def auto_run_disabled(x):
    "Auto run disabled for this node."
    print(f"Run on depand. Input: {x}")
    return {"x": x}


GROUP = plynx.node.utils.Group(
    title="Test basics",
    items=[
        make_int,
        example_func,
        sleep,
        error,
        Statefull,
        auto_run_disabled,
    ]
)
