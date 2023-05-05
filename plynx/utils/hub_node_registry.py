"""Global Node Registry class"""
import logging
from typing import List

from plynx.db.node import Node


class Registry:
    """The class keeps record of built-in Operations"""
    def __init__(self):
        self.code_function_location_to_node = {}
        self.code_function_location_to_hash = {}

    def register_node(self, node: Node):
        """Register Node globally"""
        assert node.code_function_location, "`code_function_location` is not defined. Is this node from static list?"
        self.code_function_location_to_node[node.code_function_location] = node
        self.code_function_location_to_hash[node.code_function_location] = node.code_hash
        logging.warning(f"Registered operation with location `{node.code_function_location}`")

    def find_nodes(self, function_locations: List[str]) -> List[Node]:
        """Find the Nodes"""
        res = []
        for f_location in function_locations:
            if f_location not in self.code_function_location_to_node:
                continue
            res.append(self.code_function_location_to_node[f_location])
        return res


registry = Registry()
