from pymongo import ReturnDocument
from past.builtins import basestring
from collections import OrderedDict
from plynx.constants import NodeRunningStatus
from plynx.utils.common import to_object_id, parse_search_string
from plynx.utils.db_connector import get_db_connector


class NodeCollectionManager(object):
    """NodeCollectionManager contains all the operations to work with Nodes in the database."""

    def __init__(self, collection):
        super(NodeCollectionManager, self).__init__()

        self.collection = collection

    def get_db_nodes(self, status='', node_kinds=None, search='', per_page=20, offset=0, user_id=None, is_graph=None, **fields):
        """Get subset of the Nodes.

        Args:
            status              (str, None):                Node Running Status
            base_node_names     (str, list of str, None):   Node Running Status
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
            and_query['kinds'] = {'$in': node_kinds}
        if status:
            and_query['node_status'] = {'$in': status}
        if search_string:
            and_query['$text'] = {'$search': search_string}
        if 'original_node_id' in  search_parameters:
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

    def get_db_nodes_by_ids(self, ids):
        """Find all the Nodes with a given IDs.

        Args:
            ids    (list of ObjectID):  Node Ids
        """
        db_nodes = get_db_connector()[self.collection].find({
            '_id': {
                '$in': list(ids)
            }
        })

        return list(db_nodes)

    def get_db_node(self, node_id, user_id=None):
        """Get dict representation of the Graph.

        Args:
            node_id     (ObjectId, str):        Node ID
            user_id     (str, ObjectId, None):  User ID

        Return:
            (dict)  dict representation of the Graph
        """
        res = get_db_connector()[self.collection].find_one({'_id': to_object_id(node_id)})
        if res:
            res['_readonly'] = (user_id != to_object_id(res['author']))
        return res

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
                        'node_running_status': NodeRunningStatus.READY
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
