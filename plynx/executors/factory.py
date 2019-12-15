import pydoc
import plynx.utils.exceptions
from plynx.db.node import Node


def materialize(node_dict):
    """
    Create a Node object from a dictionary

    Parameters:
    node_dict (dict): dictionary representation of a Node

    Returns:
    Node: Derived from plynx.nodes.base.Node class
    """
    kind = node_dict['kind']
    cls = pydoc.locate(kind)
    if not cls:
        raise plynx.utils.exceptions.NodeNotFound(
            'Node kind `{}` not found'.format(kind)
        )
    return pydoc.locate(kind)(Node.from_dict(node_dict))
