"""Utils to work with executors"""
from typing import Any, Dict, Union

import plynx.base.executor
import plynx.db.node
import plynx.utils.exceptions
import plynx.utils.plugin_manager


def materialize_executor(node: Union[Dict[str, Any], plynx.db.node.Node]) -> plynx.base.executor.BaseExecutor:
    """
    Create a Node object from a dictionary

    Parameters:
        node: dictionary representation of a Node or the node itself

    Returns:
        Executor: Executor based on the kind of the Node and the config
    """

    if isinstance(node, dict):
        node = plynx.db.node.Node.from_dict(node)
    cls = plynx.utils.plugin_manager.get_executor_manager().kind_to_executor_class.get(node.kind)
    if not cls:
        raise plynx.utils.exceptions.ExecutorNotFound(
            f"Node kind `{node.kind}` not found"
        )
    return cls(node)
