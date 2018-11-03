import datetime
from . import DBObject
from plynx.utils.common import to_object_id, ObjectId
from plynx.utils.db_connector import *
from plynx.constants import NodeStatus


class GraphCancellation(DBObject):
    def __init__(self, graph_cancellation_id=None):
        super(GraphCancellation, self).__init__()
        self._id = None
        self.graph_id = None
        self.acknowledged = False

        if graph_cancellation_id:
            self._id = to_object_id(graph_cancellation_id)
            self.load()

        if not self._id:
            self._id = ObjectId()

    def to_dict(self):
        return {
            "_id": self._id,
            "graph_id": self.graph_id,
            "acknowledged": self.acknowledged,
        }

    def save(self, force=False):
        assert isinstance(self._id, ObjectId)

        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        graph_cancellation_dict = self.to_dict()
        graph_cancellation_dict["update_date"] = now

        db.graphs_cancellations.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": graph_cancellation_dict
            },
            upsert=True,
        )

        self._dirty = False
        return True

    def load(self):
        graph_cancellation_dict = db.graphs_cancellations.find_one({'_id': self._id})
        self.load_from_dict(graph_cancellation_dict)

    def load_from_dict(self, graph_cancellation_dict):
        for key, value in graph_cancellation_dict.iteritems():
            setattr(self, key, graph_cancellation_dict[key])

        self._id = to_object_id(self._id)
        self._dirty = False


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
            graphs_cancellation = GraphCancellation()
            graphs_cancellation.load_from_dict(graphs_cancellation_dict)
            res.append(graphs_cancellation)
        return res

    @staticmethod
    def remove(graphs_cancellation_ids):
        db.graphs_cancellations.delete_many({'_id': {'$in': graphs_cancellation_ids}})
