"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""
"""DO NOT COMMIT"""


import json
from plynx.db.node import Node
from plynx.base import hub
from plynx.utils.common import parse_search_string
from plynx.utils.hub_node_registry import registry
from plynx.abc import COLLECTION
import plynx.node


def _enhance_list_item(raw_item):
    if raw_item['_type'] == 'Group':
        # TODO proper checking
        items = []
        for raw_subitem in raw_item['items']:
            items.append(_enhance_list_item(raw_subitem))
        raw_item['items'] = items
        return raw_item
    # check if the node is valid
    node = Node.from_dict(raw_item)
    return node.to_dict()


class StaticListHub(hub.BaseHub):
    def __init__(self, filename):
        super(StaticListHub, self).__init__()

        self.list_of_nodes = []
        for func in COLLECTION:
            obj_dict = plynx.node.utils.func_to_dict(func)
            obj = Node.from_dict(obj_dict)
            # print(json.dumps(obj, indent=4, sort_keys=True))
            registry.register_node(obj)
            self.list_of_nodes.append(obj_dict)

    def search(self, query):
        # TODO use search_parameters
        # TODO should parse_search_string be removed from nodes_collection?
        _, search_string = parse_search_string(query.search)

        def filter_func(raw_node):
            return len(search_string) == 0 or \
                search_string.upper() in raw_node['title'].upper()
        res = list(filter(
            filter_func,
            self.list_of_nodes
        ))
        return {
            'list': res,
            'metadata': [
                {
                    'total': len(res)
                },
            ],
        }
