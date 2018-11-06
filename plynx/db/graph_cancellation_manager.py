import datetime
from . import DBObject, DBObjectField
from plynx.utils.common import to_object_id, ObjectId
from plynx.utils.db_connector import *
from plynx.constants import NodeStatus


class GraphCancellation(DBObject):
    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        "graph_id": DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        "acknowledged": DBObjectField(
            type=bool,
            default=False,
            is_list=False,
            ),
    }
    DB_COLLECTION = 'graphs_cancellations'


class GraphCancellationManager(object):
    """
    """
    @staticmethod
    def cancel_graph(graph_id):
        graph_cancellation = GraphCancellation()
        graph_cancellation.graph_id = graph_id
        graph_cancellation.save()
        return True

    @staticmethod
    def get_new_graph_cancellations():
        res = []
        for graphs_cancellation_dict in db.graphs_cancellations.find():
            res.append(
                GraphCancellation.from_dict(graphs_cancellation_dict)
            )
        return res

    @staticmethod
    def remove(graphs_cancellation_ids):
        db.graphs_cancellations.delete_many({'_id': {'$in': graphs_cancellation_ids}})
