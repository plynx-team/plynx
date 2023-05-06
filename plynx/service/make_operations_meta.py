"""Create metadata of operations"""
import pydoc
from typing import Callable, Dict, List, Union

import plynx
from plynx.utils.common import JSONEncoder


def _enhance_list_item(raw_item: Dict) -> Dict:
    if raw_item['_type'] == 'Group':
        # TODO proper checking
        items = []
        for raw_subitem in raw_item['items']:
            items.append(_enhance_list_item(raw_subitem))
        raw_item['items'] = items
        return raw_item
    return raw_item


def run_make_operations_meta(collection_module, out):
    """Make metadata"""
    print(collection_module)
    for include_module in collection_module:
        collection: List[Union[Callable, plynx.node.utils.Group]] = pydoc.locate(include_module)    # type: ignore
        if collection is None:
            raise ValueError(f"Cannot open include_module=`{include_module}`. It must be a valid import value.")

        list_of_nodes = []
        for func_or_group in collection:
            raw_item = plynx.node.utils.func_or_group_to_dict(func_or_group)
            list_of_nodes.append(_enhance_list_item(raw_item))

        with open(out, "w") as f:
            json_data = JSONEncoder().encode(list_of_nodes)
            f.write(json_data)
