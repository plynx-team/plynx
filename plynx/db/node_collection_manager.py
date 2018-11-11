from past.builtins import basestring
from plynx.utils.common import to_object_id
from plynx.utils.db_connector import get_db_connector


class NodeCollectionManager(object):
    """NodeCollectionManager contains all the operations to work with Nodes in the database."""

    @staticmethod
    def _get_basic_query(author, status, base_node_names, search):
        if status and isinstance(status, basestring):
            status = [status]
        if base_node_names and isinstance(base_node_names, basestring):
            base_node_names = [base_node_names]

        and_query = []
        and_query.append({
            '$or': [
                {'author': author},
                {'public': True}
            ]})
        if base_node_names:
            and_query.append({'base_node_name': {'$in': base_node_names}})
        if status:
            and_query.append({'node_status': {'$in': status}})
        if search:
            and_query.append({'$text': {'$search': search}})

        return and_query

    # TODO remove `author` / make default
    @staticmethod
    def get_db_nodes(author, status=None, base_node_names=None, search=None, per_page=20, offset=0):
        """Get subset of the Nodes.

        Args:
            author              (ObjectId):                 Author of the Nodes
            status              (str, None):                Node Running Status
            base_node_names     (str, list of str, None):   Node Running Status
            search              (str, None):                Search pattern
            per_page            (int):                      Number of Nodes per page
            offset              (int):                      Offset

        Return:
            (list of dict)  List of Nodes in dict format
        """
        and_query = NodeCollectionManager._get_basic_query(
            author=author,
            status=status,
            base_node_names=base_node_names,
            search=search
        )

        db_nodes = get_db_connector().nodes.find({
            '$and': and_query
        }).sort('insertion_date', -1).skip(offset).limit(per_page)

        res = []
        for node in db_nodes:
            node['_readonly'] = (author != to_object_id(node['author']))
            res.append(node)
        return res

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
    def get_db_nodes_count(author, status=None, base_node_names=None, search=None):
        """Get number of the Nodes with given conditions.

        Args:
            author              (ObjectId):                 Author of the Nodes
            status              (str, None):                Node Running Status
            base_node_names     (str, list of str, None):   Node Running Status
            search              (str, None):                Search pattern

        Return:
            (int)   Number of Nodes
        """
        and_query = NodeCollectionManager._get_basic_query(
            author=author,
            status=status,
            base_node_names=base_node_names,
            search=search,
        )

        return get_db_connector().nodes.count({
            '$and': and_query
        })

    @staticmethod
    def get_db_node(node_id, author=None):
        """Get dict representation of the Graph.

        Args:
            node_id     (ObjectId, str):        Node ID
            author      (str, ObjectId, None):  Author ID

        Return:
            (dict)  dict representation of the Graph
        """
        res = get_db_connector().nodes.find_one({'_id': to_object_id(node_id)})
        if res:
            res['_readonly'] = (author != to_object_id(res['author']))
        return res
