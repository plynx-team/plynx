from past.builtins import basestring
from collections import OrderedDict
from plynx.utils.common import to_object_id, parse_search_string
from plynx.utils.db_connector import get_db_connector


class NodeCollectionManager(object):
    """NodeCollectionManager contains all the operations to work with Nodes in the database."""

    @staticmethod
    def get_db_nodes(status=None, base_node_names=None, search='', per_page=20, offset=0):
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
        if base_node_names and isinstance(base_node_names, basestring):
            base_node_names = [base_node_names]

        aggregate_list = []
        search_parameters, search_string = parse_search_string(search)

        # Match
        and_query = {}
        if base_node_names:
            and_query['base_node_name'] = {'$in': base_node_names}
        if status:
            and_query['node_status'] = {'$in': status}
        if search_string:
            and_query['$text'] = {'$search': search_string}
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
        # counts and pagination
        aggregate_list.append({
            '$facet': {
                "metadata": [{"$count": "total"}],
                "list": [{"$skip": offset}, {"$limit": per_page}],
            }
        })

        return next(get_db_connector().nodes.aggregate(aggregate_list), None)

    @staticmethod
    def get_db_nodes_by_ids(ids):
        """Find all the Nodes with a given IDs.

        Args:
            ids    (list of ObjectID):  Node Ids
        """
        db_nodes = get_db_connector().nodes.find({
            '_id': {
                '$in': list(ids)
            }
        })

        return list(db_nodes)

    @staticmethod
    def get_db_node(node_id, user_id=None):
        """Get dict representation of the Graph.

        Args:
            node_id     (ObjectId, str):        Node ID
            user_id     (str, ObjectId, None):  User ID

        Return:
            (dict)  dict representation of the Graph
        """
        res = get_db_connector().nodes.find_one({'_id': to_object_id(node_id)})
        if res:
            res['_readonly'] = (user_id != to_object_id(res['author']))
        return res
