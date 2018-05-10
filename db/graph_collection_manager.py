from . import Graph, BlockCollectionManager, FileCollectionManager
from utils.common import to_object_id
from utils.db_connector import *


class GraphCollectionManager(object):
    """
    """

    bcm = BlockCollectionManager()
    fcm = FileCollectionManager()

    @staticmethod
    def _update_block_statuses(db_graph):
        """
        block_ids = set(
            [to_object_id(block['derived_from']) for block in db_graph['blocks'] if block['_type'] == 'block']
            )
        db_blocks = GraphCollectionManager.bcm.get_db_blocks_by_ids(block_ids)

        file_ids = set(
            [to_object_id(file['derived_from']) for file in db_graph['blocks'] if file['_type'] == 'file']
            )
        db_files = GraphCollectionManager.fcm.get_db_files_by_ids(file_ids)

        node_id_to_db_node = {
            db_node['_id']: db_node for db_node in db_blocks + db_files
        }

        for g_block in db_graph['blocks']:
            id = to_object_id(g_block['derived_from'])
            if id in node_id_to_db_node:
                db_node = node_id_to_db_node[id]
                g_block['block_status'] = db_node['block_status']
"""
        return db_graph

    @staticmethod
    def get_graphs(graph_running_status):
        db_graphs = db.graphs.find({'graph_running_status': graph_running_status})
        graphs = []
        for db_graph in db_graphs:
            graphs.append(Graph())
            graphs[-1].load_from_dict(db_graph)
        return graphs

    @staticmethod
    def get_db_graphs(author, per_page=20, offset=0):
        db_graphs = db.graphs.find({
                '$or': [
                    {'author': author},
                    {'public': True}
                ]
                }).sort('insertion_date', -1).skip(offset).limit(per_page)
        return list(db_graphs)

    @staticmethod
    def get_db_graphs_count(author):
        return db.graphs.count({
                '$or': [
                    {'author': author},
                    {'public': True}
                ]
                })

    @staticmethod
    def get_db_graph(graph_id):
        return GraphCollectionManager._update_block_statuses(
            db.graphs.find_one({'_id': to_object_id(graph_id)})
            )
