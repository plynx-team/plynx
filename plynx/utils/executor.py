import plynx.db.node
import plynx.utils.exceptions


def materialize_executor(node_dict):
    """
    Create a Node object from a dictionary

    Parameters:
    node_dict (dict): dictionary representation of a Node

    Returns:
    Node: Derived from plynx.nodes.base.Node class
    """
    # TODO don't use late import
    from plynx.plugins.managers import executor_manager
    kind = node_dict['kind']
    cls = executor_manager.kind_to_executor_class.get(kind)
    if not cls:
        raise plynx.utils.exceptions.NodeNotFound(
            'Node kind `{}` not found'.format(kind)
        )
    return cls(plynx.db.node.Node.from_dict(node_dict))
