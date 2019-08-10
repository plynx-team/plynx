from builtins import str
from distutils.util import strtobool
from plynx.db.graph import Graph
from plynx.db.node import Node
from plynx.db.node_collection_manager import NodeCollectionManager
from plynx.utils.common import to_object_id, parse_search_string
from plynx.utils.db_connector import get_db_connector
from plynx.constants import NodeStatus


class GraphCollectionManager(object):
    """GraphCollectionManager contains all the operations to work with Graphs in the database."""

    node_collection_manager = NodeCollectionManager()

    @staticmethod
    def _update_node_statuses(db_graph):
        if not db_graph:
            return None
        node_ids = set(
            [to_object_id(node['parent_node']) for node in db_graph['nodes']]
        )
        db_nodes = GraphCollectionManager.node_collection_manager.get_db_nodes_by_ids(node_ids)

        node_id_to_db_node = {
            db_node['_id']: db_node for db_node in db_nodes
        }

        for g_node in db_graph['nodes']:
            id = to_object_id(g_node['parent_node'])
            if id in node_id_to_db_node:
                db_node = node_id_to_db_node[id]
                g_node['node_status'] = db_node['node_status']

        return db_graph

    @staticmethod
    def _transplant_node(node, new_node):
        if to_object_id(node.parent_node) == new_node._id:
            return node
        new_node.apply_properties(node)
        new_node.parent_node = str(new_node._id)
        new_node._id = node._id
        return new_node

    @staticmethod
    def upgrade_nodes(graph):
        """Upgrade deprecated Nodes.

        The function does not change the Graph in the database.

        Return:
            (int)   Number of upgraded Nodes
        """
        node_ids = set(
            [to_object_id(node.parent_node) for node in graph.nodes]
        )
        db_nodes = GraphCollectionManager.node_collection_manager.get_db_nodes_by_ids(node_ids)
        new_node_db_mapping = {}

        for db_node in db_nodes:
            original_parent_node_id = db_node['_id']
            new_db_node = db_node
            if original_parent_node_id not in new_node_db_mapping:
                while new_db_node['node_status'] != NodeStatus.READY and 'successor_node' in new_db_node and new_db_node['successor_node']:
                    n = GraphCollectionManager.node_collection_manager.get_db_node(new_db_node['successor_node'])
                    if n:
                        new_db_node = n
                    else:
                        break
                new_node_db_mapping[original_parent_node_id] = new_db_node

        new_nodes = [
            GraphCollectionManager._transplant_node(
                node,
                Node.from_dict(new_node_db_mapping[to_object_id(node.parent_node)])
            ) for node in graph.nodes]

        upgraded_nodes_count = sum(
            1 for node, new_node in zip(graph.nodes, new_nodes) if node.parent_node != new_node.parent_node
        )

        graph.nodes = new_nodes
        return upgraded_nodes_count

    @staticmethod
    def get_graphs(graph_running_status):
        """Find all the Graphs with a given graph_running_status.

        Args:
            graph_running_status    (str):  Graph Running Status
        """
        db_graphs = get_db_connector().graphs.find({'graph_running_status': graph_running_status})
        graphs = []
        for db_graph in db_graphs:
            graphs.append(Graph.from_dict(db_graph))
        return graphs

    @staticmethod
    def get_db_graphs(search='', per_page=20, offset=0, status=None):
        """Get subset of the Graphs.

        Args:
            search      (str):          Search pattern
            per_page    (int):          Number of Graphs per page
            offset      (int):          Offset

        Return:
            (list of dicts)     List of Graphs in dict format
        """
        if status and isinstance(status, str):
            status = [status]

        aggregate_list = []
        search_parameters, search_string = parse_search_string(search)

        # Match
        and_query = {}
        if status:
            and_query['graph_running_status'] = {'$in': status}
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
        sort_key = search_parameters.get('order', 'insertion_date')
        try:
            sort_order = -1 if strtobool(search_parameters.get('desc', '1')) else 1
        except ValueError:
            sort_order = -1
        aggregate_list.append({
            "$sort": {sort_key: sort_order}
            }
        )
        # counts and pagination
        aggregate_list.append({
            '$facet': {
                "metadata": [{"$count": "total"}],
                "list": [{"$skip": int(offset)}, {"$limit": int(per_page)}],
            }
        })

        return next(get_db_connector().graphs.aggregate(aggregate_list), None)

    @staticmethod
    def get_db_graph(graph_id, user_id=None):
        """Get dict representation of the Graph.

        Args:
            graph_id    (ObjectId, str):    Graph ID
            user_id     (str, ObjectId, None):  User ID

        Return:
            (dict)  dict representation of the Graph
        """
        res = GraphCollectionManager._update_node_statuses(
            get_db_connector().graphs.find_one({'_id': to_object_id(graph_id)})
        )
        if res:
            res['_readonly'] = (to_object_id(user_id) != to_object_id(res['author']))
        return res
