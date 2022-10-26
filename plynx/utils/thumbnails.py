"""Thumbnail utils"""
import logging
from typing import Optional

import plynx.db.node
import plynx.utils.plugin_manager
from plynx.constants import NodeRunningStatus


def get_thumbnail(output: plynx.db.node.Output) -> Optional[str]:
    """Apply a single thumbnail"""
    cls = plynx.utils.plugin_manager.get_resource_manager().kind_to_resource_class[output.file_type]
    if not cls.DISPLAY_THUMBNAIL:
        return None
    return cls.thumbnail(output)


def apply_thumbnails(node: plynx.db.node.Node):
    """
    Fill thumbnail field of every subnode
    """
    sub_nodes_parameter = node.get_parameter_by_name('_nodes', throw=False)
    if not sub_nodes_parameter:
        logging.warning("no subnodes found in `apply_thumbnails`")
        return

    sub_nodes = sub_nodes_parameter.value.value

    for sub_node in sub_nodes:
        if NodeRunningStatus.is_succeeded(sub_node.node_running_status):
            for output in sub_node.outputs:
                output.thumbnail = get_thumbnail(output)
        if sub_node._cached_node:
            for output in sub_node._cached_node.outputs:
                output.thumbnail = get_thumbnail(output)
