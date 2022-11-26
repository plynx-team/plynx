"""Node collection manager and utils"""

import logging
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union

from past.builtins import basestring
from pymongo import ReturnDocument

from plynx.constants import Collections, HubSearchParams, NodeRunningStatus, NodeStatus
from plynx.db.node import Node
from plynx.utils.common import ObjectId, parse_search_string, to_object_id
from plynx.utils.db_connector import get_db_connector
from plynx.utils.hub_node_registry import registry

_PROPERTIES_TO_GET_FROM_SUBS = ['node_running_status', 'logs', 'outputs', 'cache_url']


class NodeCollectionManager:
    """NodeCollectionManager contains all the operations to work with Nodes in the database."""

    def __init__(self, collection: str):
        super().__init__()

        self.collection: str = collection

    # pylint: disable=too-many-arguments
    def get_db_objects(
            self,
            status: Union[List[str], str] = '',
            node_kinds: Union[None, str, List[str]] = None,
            search: str = '',
            per_page: int = 20,
            offset: int = 0,
            user_id: Optional[ObjectId] = None,
            ) -> Optional[List[Dict]]:
        """Get subset of the Objects.

        Args:
            status              (str, None):                Node Running Status
            search              (str, None):                Search pattern
            per_page            (int):                      Number of Nodes per page
            offset              (int):                      Offset

        Return:
            (list of dict)  List of Nodes in dict format
        """
        # pylint: disable=too-many-branches
        if status and isinstance(status, basestring):
            status = [status]
        if node_kinds and isinstance(node_kinds, basestring):
            node_kinds = [node_kinds]

        aggregate_list: List[Dict[str, Any]] = []
        search_parameters, search_string = parse_search_string(search)

        # Match
        and_query: Dict[str, Union[ObjectId, Dict[str, Union[str, List[str], Dict]]]] = {}
        if node_kinds:
            and_query['kind'] = {'$in': node_kinds}
        if status:
            and_query['node_status'] = {'$in': status}
        if search_string:
            and_query['$text'] = {'$search': search_string}
        if 'original_node_id' in search_parameters:
            and_query['original_node_id'] = to_object_id(search_parameters['original_node_id'])
        if HubSearchParams.INPUT_FILE_TYPE in search_parameters:
            and_query['inputs'] = {"$elemMatch": {"file_type": search_parameters[HubSearchParams.INPUT_FILE_TYPE]}}
        if HubSearchParams.OUTPUT_FILE_TYPE in search_parameters:
            and_query['outputs'] = {"$elemMatch": {"file_type": search_parameters[HubSearchParams.OUTPUT_FILE_TYPE]}}
        if len(and_query) > 0:
            aggregate_list.append({"$match": and_query})

        # Join with users
        aggregate_list.append({
            '$lookup': {
                'from': 'users',
                'localField': 'author',
                'foreignField': '_id',
                'as': '_user'
            }
        })
        # rm password hash
        aggregate_list.append({
          "$project": {
            "_user.password_hash": 0,
          }
        })

        # Match username
        and_query = {}
        if 'author' in search_parameters:
            and_query['_user.username'] = search_parameters['author']

        if len(and_query):
            aggregate_list.append({"$match": and_query})

        # sort
        sort_dict = OrderedDict()
        if 'sort' in search_parameters:
            # TODO more sort options
            if search_parameters['sort'] == 'starred':
                sort_dict['starred'] = -1
        sort_dict['insertion_date'] = -1

        aggregate_list.append({
            "$sort": sort_dict
            }
        )
        aggregate_list.append({
            "$addFields": {
                '_readonly': {'$ne': ["$author", to_object_id(user_id)]},
            }
        })
        # counts and pagination
        aggregate_list.append({
            '$facet': {
                "metadata": [{"$count": "total"}],
                "list": [{"$skip": int(offset)}, {"$limit": int(per_page)}],
            }
        })

        # TODO: remove `allowDiskUse=True` and update indexes instead
        return next(get_db_connector()[self.collection].aggregate(aggregate_list, allowDiskUse=True), None)

    def get_db_objects_by_ids(self, ids: Union[List[ObjectId], List[str]], collection: Optional[str] = None) -> List[dict]:
        """Find all the Objects with a given IDs.

        Args:
            ids    (list of ObjectID):  Object Ids
        """
        if collection == Collections.HUB_NODE_REGISTRY:
            # TODO separate types of ids into different functions
            db_objects = map(lambda node: node.to_dict(), registry.find_nodes(ids))     # type: ignore
        else:
            db_objects = get_db_connector()[collection or self.collection].find({
                '_id': {
                    '$in': list(ids)
                }
            })

        return list(db_objects)

    def _update_sub_nodes_fields(
            self,
            sub_nodes_dicts: List[Dict],
            reference_node_id: str,
            target_props: List[str],
            reference_collection: Optional[str] = None
            ):
        reference_collection = reference_collection or self.collection
        id_to_updated_node_dict = {}
        function_location_to_updated_node_dict = {}
        upd_node_ids = list(map(lambda node_dict: node_dict.get(reference_node_id, "unknown"), sub_nodes_dicts))
        for upd_node_dict in self.get_db_objects_by_ids(upd_node_ids, collection=reference_collection):
            id_to_updated_node_dict[upd_node_dict['_id']] = upd_node_dict
            function_location_to_updated_node_dict[upd_node_dict.get("code_function_location", "unknown")] = upd_node_dict
        for sub_node_dict in sub_nodes_dicts:
            if sub_node_dict.get(reference_node_id, "unknown") not in id_to_updated_node_dict:
                continue
            for prop in target_props:
                sub_node_dict[prop] = id_to_updated_node_dict[sub_node_dict.get(reference_node_id, "unknown")][prop]

        if reference_collection == Collections.HUB_NODE_REGISTRY:
            # special case: we need to compare not target_props, but rather assign it
            assert len(target_props) == 1, "Only node_status can be assigned"
            assert target_props[0] == 'node_status', "Only node_status can be assigned"
            for sub_node_dict in sub_nodes_dicts:
                if sub_node_dict.get(reference_node_id, "unknown") is None:
                    continue
                if sub_node_dict.get(reference_node_id, "unknown") not in function_location_to_updated_node_dict:
                    logging.warning(f"`{sub_node_dict.get(reference_node_id, 'unknown')}` is not found in the list of operation locations")
                    continue
                if sub_node_dict['code_hash'] != function_location_to_updated_node_dict[sub_node_dict.get(reference_node_id, "unknown")]["code_hash"]:
                    sub_node_dict['node_status'] = NodeStatus.DEPRECATED

    def get_db_node(self, node_id: ObjectId, user_id: Optional[ObjectId] = None):
        """Get dict representation of a Node.

        Args:
            node_id     (ObjectId, str):        Object ID
            user_id     (str, ObjectId, None):  User ID

        Return:
            (dict)  dict representation of the Object
        """
        res = self.get_db_object(node_id, user_id)
        if not res:
            return res

        sub_nodes_dicts: Optional[List[Dict]] = None
        for parameter in res['parameters']:
            if parameter['name'] == '_nodes':
                sub_nodes_dicts = parameter['value']['value']
                break

        if sub_nodes_dicts:
            # TODO join collections using database capabilities
            if self.collection == Collections.RUNS:
                self._update_sub_nodes_fields(sub_nodes_dicts, '_id', _PROPERTIES_TO_GET_FROM_SUBS)
            self._update_sub_nodes_fields(sub_nodes_dicts, 'original_node_id', ['node_status'], reference_collection=Collections.TEMPLATES)
            self._update_sub_nodes_fields(sub_nodes_dicts, 'code_function_location', ['node_status'], reference_collection=Collections.HUB_NODE_REGISTRY)

        return res

    def get_db_object(self, object_id: ObjectId, user_id: Optional[ObjectId] = None) -> Dict:
        """Get dict representation of an Object.

        Args:
            object_id   (ObjectId):        Object ID
            user_id     (ObjectId, None):  User ID

        Return:
            (dict)  dict representation of the Object
        """
        res = get_db_connector()[self.collection].find_one({'_id': to_object_id(object_id)})
        if not res:
            return res

        res['_readonly'] = (user_id != to_object_id(res['author']))

        return res

    @staticmethod
    def _transplant_node(node: Node, dest_node: Node) -> Node:
        if dest_node._id == node.original_node_id:
            return node
        dest_node.apply_properties(node)
        dest_node.original_node_id = dest_node._id
        dest_node.parent_node_id = dest_node.successor_node_id = None
        dest_node._id = node._id
        return dest_node

    def upgrade_sub_nodes(self, main_node: Node) -> int:
        """Upgrade deprecated Nodes.

        The function does not change the original graph in the database.

        Return:
            (int):  Number of upgraded Nodes
        """
        assert self.collection == Collections.TEMPLATES
        sub_nodes = main_node.get_parameter_by_name('_nodes').value.value
        node_ids = [node.original_node_id for node in sub_nodes]
        db_nodes = self.get_db_objects_by_ids(node_ids)
        new_node_db_mapping = {}

        for db_node in db_nodes:
            original_node_id = db_node['_id']
            new_db_node = db_node
            if original_node_id not in new_node_db_mapping:
                while new_db_node['node_status'] != NodeStatus.READY and 'successor_node_id' in new_db_node and new_db_node['successor_node_id']:
                    tmp_node = self.get_db_node(new_db_node['successor_node_id'])
                    if tmp_node:
                        new_db_node = tmp_node
                    else:
                        break
                new_node_db_mapping[original_node_id] = new_db_node

        new_nodes = [
            NodeCollectionManager._transplant_node(
                node,
                Node.from_dict(new_node_db_mapping[to_object_id(node.original_node_id)])
            ) for node in sub_nodes]

        upgraded_nodes_count = sum(
            1 for node, new_node in zip(sub_nodes, new_nodes) if node.original_node_id != new_node.original_node_id
        )

        main_node.get_parameter_by_name('_nodes').value.value = new_nodes
        return upgraded_nodes_count

    def pick_node(self, kinds: List[str]) -> Dict:
        """Get node and set status to RUNNING in atomic way"""
        node = get_db_connector()[self.collection].find_one_and_update(
            {
                '$and': [
                    {
                        'kind': {
                            '$in': kinds,
                        }
                    },
                    {
                        'node_running_status': {
                            '$in': [
                                NodeRunningStatus.READY,
                                NodeRunningStatus.IN_QUEUE,
                            ]
                        }
                    },
                ],
            },
            {
                '$set': {
                    'node_running_status': NodeRunningStatus.RUNNING
                }
            },
            return_document=ReturnDocument.AFTER
        )
        return node
