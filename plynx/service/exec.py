import json
import plynx.executors.factory as factory


def run_exec(filename):
    with open(filename) as f:
        node = factory.materialize(json.load(f))
    node.run()
    print('Success')
    return 0
