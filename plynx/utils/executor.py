"""Utils to work with executors"""
from typing import Any, Dict

import plynx.db.node
import plynx.utils.exceptions
import plynx.utils.plugin_manager


def materialize_executor(node_dict: Dict[str, Any]):
    """
    Create a Node object from a dictionary

    Parameters:
    node_dict (dict): dictionary representation of a Node

    Returns:
    Node: Derived from plynx.nodes.base.Node class
    """
    node = plynx.db.node.Node.from_dict(node_dict)
    cls = plynx.utils.plugin_manager.get_executor_manager().kind_to_executor_class.get(node.kind)
    if not cls:
        raise plynx.utils.exceptions.ExecutorNotFound(
            f"Node kind `{node.kind}` not found"
        )
    return cls(node)
