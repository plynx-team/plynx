import json
from plynx.db.node import Node
from plynx.base import hub
from plynx.utils.common import parse_search_string


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

        with open(filename) as f:
            data_list = json.load(f)
            for raw_item in data_list:
                self.list_of_nodes.append(_enhance_list_item(raw_item))

    def search(self, query):
        # TODO use search_parameters
        # TODO should parse_search_string be removed from nodes_collection?
        _, search_string = parse_search_string(query.search)

        def filter_func(raw_node):
            return len(search_string) == 0 or \
                search_string.upper() in raw_node['title'].upper() or \
                search_string.upper() in raw_node['description'].upper()
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
