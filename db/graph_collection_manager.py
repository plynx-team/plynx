from . import Graph
from utils.common import to_object_id
from utils.db_connector import *

class GraphCollectionManager(object):
    """
    """

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
        return db.graphs.find_one({'_id': to_object_id(graph_id)})