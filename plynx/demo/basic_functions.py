import math
import time
import random
import sys

import plynx.node


@plynx.node.param(name='value', var_type=int, default=1)
@plynx.node.output(name='x', var_type=int)
@plynx.node.operation(
    title="Make integer"
)
def make_int(value):
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
    raise Exception("Expected exception")
    return {
        "x": sum(x) + 1
    }


@plynx.node.input(name='x', var_type=int, is_array=True, min_count=0)
@plynx.node.output(name='x', var_type=int)
@plynx.node.operation(
    title="Stateful sum",
    description="Add 1 and keep the previous value",
)
class Statefull:
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


GROUP = plynx.node.utils.Group(
    title="Test basics",
    items=[
        make_int,
        example_func,
        sleep,
        error,
        Statefull,
    ]
)
