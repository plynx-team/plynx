import datetime
from db.db_object import DBObject
from utils.db_connector import *
from utils.common import to_object_id
from bson.objectid import ObjectId

class Graph(DBObject):
    """
    Basic graph with db interface
    """

    blocks = []
    _id = None
    title = None

    def __init__(self, graph_id=None):
        if graph_id:
            self._id = to_object_id(graph_id)
            self.load()
        else:
            self.dirty = True

    def save(self):
        if not self.is_dirty():
            return True

        now = datetime.datetime.utcnow()

        if not self._id:
            self._id = ObjectId()

        db.graphs.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": {
                    "title": self.title,
                    'update_date': now
                },
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self):
        graph = db.graphs.find_one({'_id': self._id})

        for key, value in graph.iteritems():
            setattr(self, key, graph[key])

        self._dirty = False


if __name__ == "__main__":
    graph = Graph()
    graph.title = "Test graph"
    graph.save()
