import json
from plynx.utils import executor


def run_execute(filename):
    with open(filename) as f:
        node = executor.materialize_executor(json.load(f))
    node.run()
    print('Success')
    return 0
