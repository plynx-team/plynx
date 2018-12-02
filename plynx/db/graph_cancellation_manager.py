from plynx.db import DBObject, DBObjectField
from plynx.constants import Collections
from plynx.utils.common import ObjectId
from plynx.utils.db_connector import get_db_connector


class GraphCancellation(DBObject):
    """GraphCancellation represents Graph Cancellation event in the database."""

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

    DB_COLLECTION = Collections.GRAPHS_CANCELLATIONS


class GraphCancellationManager(object):
    """GraphCancellationManager contains basic operations related to `graphs_cancellations` collection."""

    @staticmethod
    def cancel_graph(graph_id):
        """Cancel Graph.

        Args:
            graph_id    (ObjectId, str) GraphID
        """
        graph_cancellation = GraphCancellation()
        graph_cancellation.graph_id = ObjectId(graph_id)
        graph_cancellation.save()
        return True

    @staticmethod
    def get_graph_cancellations():
        """Get all Graph Cancellation events"""
        res = []
        for graphs_cancellation_dict in get_db_connector().graphs_cancellations.find():
            res.append(
                GraphCancellation.from_dict(graphs_cancellation_dict)
            )
        return res

    @staticmethod
    def remove(graphs_cancellation_ids):
        """Remove Graph Cancellation events with given Ids

        Args:
            graphs_cancellation_ids     (list of ObjectID)  List of Graph IDs to remove
        """
        get_db_connector().graphs_cancellations.delete_many({'_id': {'$in': graphs_cancellation_ids}})
