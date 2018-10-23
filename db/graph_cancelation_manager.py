import datetime
from . import DBObject
from utils.common import to_object_id, ObjectId
from utils.db_connector import *
from constants import NodeStatus


class GraphCancelation(DBObject):
    def __init__(self, graph_cancelation_id=None):
        super(GraphCancelation, self).__init__()
        self._id = None
        self.graph_id = None
        self.acknowledged = False

        if graph_cancelation_id:
            self._id = to_object_id(graph_cancelation_id)
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

        graph_cancelation_dict = self.to_dict()
        graph_cancelation_dict["update_date"] = now

        db.graphs_cancelations.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": graph_cancelation_dict
            },
            upsert=True,
        )

        self._dirty = False
        return True

    def load(self):
        graph_cancelation_dict = db.graphs_cancelations.find_one({'_id': self._id})
        self.load_from_dict(graph_cancelation_dict)

    def load_from_dict(self, graph_cancelation_dict):
        for key, value in graph_cancelation_dict.iteritems():
            setattr(self, key, graph_cancelation_dict[key])

        self._id = to_object_id(self._id)
        self._dirty = False


class GraphCancelationManager(object):
    """
    """
    @staticmethod
    def cancel_graph(graph_id):
        graph_cancelation = GraphCancelation()
        graph_cancelation.graph_id = graph_id
        graph_cancelation.save()
        return True

    @staticmethod
    def get_new_graph_cancelations():
        res = []
        for graphs_cancelation_dict in db.graphs_cancelations.find():
            graphs_cancelation = GraphCancelation()
            graphs_cancelation.load_from_dict(graphs_cancelation_dict)
            res.append(graphs_cancelation)
        return res

    @staticmethod
    def remove(graphs_cancelation_ids):
        db.graphs_cancelations.delete_many({'_id': {'$in': graphs_cancelation_ids}})
