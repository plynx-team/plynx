"""Main PLynx executor service and utils"""

import json

from plynx.utils import executor


def run_execute(filename: str):
    """Execute entrypoint. It materialize the Node based on file content and runs it."""
    with open(filename) as f:
        node = executor.materialize_executor(json.load(f))
    node.run()
    print('Success')
    return 0
