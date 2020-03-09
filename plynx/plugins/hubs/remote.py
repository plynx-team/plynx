import json
from plynx.db.node import Node
from plynx.plugins.hubs import BaseHub
from plynx.utils.common import parse_search_string


class RemoteListHub(BaseHub):
    def __init__(self, endpoint):
        super(RemoteListHub, self).__init__()
        return
        self.list_of_nodes = []

        with open(filename) as f:
            data_list = json.load(f)
            for raw_node in data_list:
                # check if the node is valid
                node = Node.from_dict(raw_node)
                self.list_of_nodes.append(node.to_dict())

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
