from pymongo import ReturnDocument
from past.builtins import basestring
from collections import OrderedDict
from plynx.db.node import Node
from plynx.constants import NodeRunningStatus, Collections, NodeStatus
from plynx.utils.common import to_object_id, parse_search_string
from plynx.utils.db_connector import get_db_connector

_PROPERTIES_TO_GET_FROM_SUBS = ['node_running_status', 'logs', 'outputs', 'cache_url']


class NodeCollectionManager(object):
    """NodeCollectionManager contains all the operations to work with Nodes in the database."""

    def __init__(self, collection):
        super(NodeCollectionManager, self).__init__()

        self.collection = collection

    def get_db_objects(
            self,
            status='',
            node_kinds=None,
            search='',
            per_page=20,
            offset=0,
            user_id=None,
            ):
        """Get subset of the Objects.

        Args:
            status              (str, None):                Node Running Status
            search              (str, None):                Search pattern
            per_page            (int):                      Number of Nodes per page
            offset              (int):                      Offset

        Return:
            (list of dict)  List of Nodes in dict format
        """
        if status and isinstance(status, basestring):
            status = [status]
        if node_kinds and isinstance(node_kinds, basestring):
            node_kinds = [node_kinds]

        aggregate_list = []
        search_parameters, search_string = parse_search_string(search)

        # Match
        and_query = {}
        if node_kinds:
            and_query['kind'] = {'$in': node_kinds}
        if status:
            and_query['node_status'] = {'$in': status}
        if search_string:
            and_query['$text'] = {'$search': search_string}
        if 'original_node_id' in search_parameters:
            and_query['original_node_id'] = to_object_id(search_parameters['original_node_id'])
        if len(and_query):
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

        return next(get_db_connector()[self.collection].aggregate(aggregate_list), None)

    def get_db_objects_by_ids(self, ids, collection=None):
        """Find all the Objects with a given IDs.

        Args:
            ids    (list of ObjectID):  Object Ids
        """
        db_objects = get_db_connector()[collection or self.collection].find({
            '_id': {
                '$in': list(ids)
            }
        })

        return list(db_objects)

    def _update_sub_nodes_fields(self, sub_nodes_dicts, reference_node_id, target_props, reference_collection=None):
        if not sub_nodes_dicts:
            return
        reference_collection = reference_collection or self.collection
        id_to_updated_node_dict = {}
        upd_node_ids = set(map(lambda node_dict: node_dict[reference_node_id], sub_nodes_dicts))
        for upd_node_dict in self.get_db_objects_by_ids(upd_node_ids, collection=reference_collection):
            id_to_updated_node_dict[upd_node_dict['_id']] = upd_node_dict
        for sub_node_dict in sub_nodes_dicts:
            if sub_node_dict[reference_node_id] not in id_to_updated_node_dict:
                continue
            for prop in target_props:
                sub_node_dict[prop] = id_to_updated_node_dict[sub_node_dict[reference_node_id]][prop]

    def get_db_node(self, node_id, user_id=None):
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

        sub_nodes_dicts = None
        for parameter in res['parameters']:
            if parameter['name'] == '_nodes':
                sub_nodes_dicts = parameter['value']['value']
                break

        # TODO join collections using database capabilities
        if self.collection == Collections.RUNS:
            self._update_sub_nodes_fields(sub_nodes_dicts, '_id', _PROPERTIES_TO_GET_FROM_SUBS)
        self._update_sub_nodes_fields(sub_nodes_dicts, 'original_node_id', ['node_status'], reference_collection=Collections.TEMPLATES)

        return res

    def get_db_object(self, object_id, user_id=None):
        """Get dict representation of an Object.

        Args:
            object_id   (ObjectId, str):        Object ID
            user_id     (str, ObjectId, None):  User ID

        Return:
            (dict)  dict representation of the Object
        """
        res = get_db_connector()[self.collection].find_one({'_id': to_object_id(object_id)})
        if not res:
            return res

        res['_readonly'] = (user_id != to_object_id(res['author']))

        return res

    @staticmethod
    def _transplant_node(node, new_node):
        if new_node._id == node.original_node_id:
            return node
        new_node.apply_properties(node)
        new_node.original_node_id = new_node._id
        new_node.parent_node_id = new_node.successor_node_id = None
        new_node._id = node._id
        return new_node

    def upgrade_sub_nodes(self, main_node):
        """Upgrade deprecated Nodes.

        The function does not change the original graph in the database.

        Return:
            (int):  Number of upgraded Nodes
        """
        assert self.collection == Collections.TEMPLATES
        sub_nodes = main_node.get_parameter_by_name('_nodes').value.value
        node_ids = set(
            [node.original_node_id for node in sub_nodes]
        )
        db_nodes = self.get_db_objects_by_ids(node_ids)
        new_node_db_mapping = {}

        for db_node in db_nodes:
            original_node_id = db_node['_id']
            new_db_node = db_node
            if original_node_id not in new_node_db_mapping:
                while new_db_node['node_status'] != NodeStatus.READY and 'successor_node_id' in new_db_node and new_db_node['successor_node_id']:
                    n = self.get_db_node(new_db_node['successor_node_id'])
                    if n:
                        new_db_node = n
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

    def pick_node(self, kinds):
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
