from plynx.db import Graph, NodeCollectionManager, Node
from plynx.utils.common import to_object_id
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
    def _get_basic_query(author, search, status):
        and_query = []
        and_query.append({
            '$or': [
                {'author': author},
                {'public': True}
            ]})
        if search:
            and_query.append({'$text': {'$search': search}})
        if status:
            and_query.append({'graph_running_status': status})

        return and_query

    # TODO remove `author` / make default
    @staticmethod
    def get_db_graphs(author, search=None, per_page=20, offset=0, status=None, recent=False):
        """Get subset of the Graphs.

        Args:
            author      (ObjectId):     Author of the Graphs
            search      (str):          Search pattern
            per_page    (int):          Number of Graphs per page
            offset      (int):          Offset

        Return:
            (list of dicts)     List of Graphs in dict format
        """
        and_query = GraphCollectionManager._get_basic_query(
            author=author,
            search=search,
            status=status,
        )
        sort_key = 'update_date' if recent else 'insertion_date'

        db_graphs = get_db_connector().graphs.find({
            '$and': and_query
        }).sort(sort_key, -1).skip(offset).limit(per_page)
        return list(db_graphs)

    @staticmethod
    def get_db_graphs_count(author, search=None, status=None):
        """Get number of the Graphs that satisfy given conditions.

        Args:
            author      (ObjectId):     Author of the Graphs
            search      (str):          Search pattern

        Return:
            (int)   Number of Graphs found.
        """
        and_query = GraphCollectionManager._get_basic_query(
            author=author,
            search=search,
            status=status,
        )
        return get_db_connector().graphs.count({
            '$and': and_query
        })

    @staticmethod
    def get_db_graph(graph_id):
        """Get dict representation of the Graph.

        Args:
            graph_id    (ObjectId, str):    Graph ID

        Return:
            (dict)  dict representation of the Graph
        """
        return GraphCollectionManager._update_node_statuses(
            get_db_connector().graphs.find_one({'_id': to_object_id(graph_id)})
        )
