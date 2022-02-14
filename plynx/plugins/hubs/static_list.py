import copy
import pydoc

from plynx.db.node import Node
from plynx.base import hub
from plynx.utils.common import parse_search_string
from plynx.utils.hub_node_registry import registry
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
    registry.register_node(node)
    return node.to_dict()


def _recursive_filter(search_string, list_of_nodes):
    res = []
    for raw_node in list_of_nodes:
        if raw_node["_type"] == "Group":
            raw_group = copy.deepcopy(raw_node)
            raw_group['items'] = _recursive_filter(search_string, raw_group['items'])
            res.append(raw_group)
        elif len(search_string) == 0 or search_string.upper() in raw_node['title'].upper():
            res.append(raw_node)
    return res


class StaticListHub(hub.BaseHub):
    def __init__(self, list_module):
        super(StaticListHub, self).__init__()

        collection = pydoc.locate(list_module)

        assert collection is not None, f"Module `{list_module}` not found"

        self.list_of_nodes = []
        for func_or_group in collection:
            raw_item = plynx.node.utils.func_or_group_to_dict(func_or_group)
            self.list_of_nodes.append(_enhance_list_item(raw_item))

    def search(self, query):
        # TODO use search_parameters
        # TODO should parse_search_string be removed from nodes_collection?
        _, search_string = parse_search_string(query.search)

        res = _recursive_filter(search_string, self.list_of_nodes)
        return {
            'list': res,
            'metadata': [
                {
                    'total': len(res)
                },
            ],
        }
