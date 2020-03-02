import json
from plynx.plugins.executors import materialize_executor


def run_execute(filename):
    with open(filename) as f:
        node = materialize_executor(json.load(f))
    node.run()
    print('Success')
    return 0
