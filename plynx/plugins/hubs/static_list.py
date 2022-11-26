"""Plynx standard Hub based on the fixed list of Operations"""

import copy
import pydoc
from typing import Any, Callable, Dict, List, Union

import plynx.node
from plynx.base import hub
from plynx.constants import HubSearchParams
from plynx.db.node import Node
from plynx.utils.common import parse_search_string
from plynx.utils.hub_node_registry import registry


def _enhance_list_item(raw_item: Dict) -> Dict:
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


def _recursive_filter(search_parameters: Dict[str, str], search_string: str, list_of_nodes: List[Dict]):
    res = []
    for raw_node in list_of_nodes:
        if raw_node["_type"] == "Group":
            raw_group = copy.deepcopy(raw_node)
            raw_group['items'] = _recursive_filter(search_parameters, search_string, raw_group['items'])
            res.append(raw_group)
        elif len(search_string) == 0 or search_string.upper() in raw_node['title'].upper():
            input_file_type = search_parameters.get(HubSearchParams.INPUT_FILE_TYPE, None)
            output_file_type = search_parameters.get(HubSearchParams.OUTPUT_FILE_TYPE, None)
            if input_file_type:
                for input in raw_node["inputs"]:    # pylint: disable=redefined-builtin
                    if input["file_type"] == input_file_type:
                        break
                else:
                    continue
            if output_file_type:
                for output in raw_node["outputs"]:
                    if output["file_type"] == output_file_type:
                        break
                else:
                    continue
            res.append(raw_node)
    return res


class StaticListHub(hub.BaseHub):
    """Plynx standard Hub based on the fixed list of Operations"""
    def __init__(self, list_module: str):
        super().__init__()

        collection: List[Union[Callable, plynx.node.utils.Group]] = pydoc.locate(list_module)   # type: ignore

        assert collection is not None, f"Module `{list_module}` not found"

        self.list_of_nodes = []
        for func_or_group in collection:
            raw_item = plynx.node.utils.func_or_group_to_dict(func_or_group)
            self.list_of_nodes.append(_enhance_list_item(raw_item))

    def search(self, query: hub.Query) -> Dict[str, Any]:
        # TODO use search_parameters
        # TODO should parse_search_string be removed from nodes_collection?
        search_parameters, search_string = parse_search_string(query.search)

        res = _recursive_filter(search_parameters, search_string, self.list_of_nodes)
        return {
            'list': res,
            'metadata': [
                {
                    'total': len(res)
                },
            ],
        }
