import datetime
from . import Block, DBObject
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import GraphRunningStatus


class Graph(DBObject):
    """
    Basic graph with db interface
    """

    def __init__(self, graph_id=None):
        super(Graph, self).__init__()
        self._id = None
        self.title = 'Title'
        self.description = 'Description'
        self.graph_running_status = GraphRunningStatus.CREATED
        self.blocks = []

        if graph_id:
            self._id = to_object_id(graph_id)
            self.load()

        if not self._id:
            self._id = ObjectId()

    def to_dict(self):
        return {
            "_id": self._id,
            "title": self.title,
            "description": self.description,
            "graph_running_status": self.graph_running_status,
            "blocks": [block.to_dict() for block in self.blocks]
        }

    def save(self, force=False):
        assert isinstance(self._id, ObjectId)

        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        graph_dict = self.to_dict()
        graph_dict["update_date"] = now

        db.graphs.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": graph_dict
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self):
        graph = db.graphs.find_one({'_id': self._id})
        self.load_from_mongo(graph)

    def load_from_mongo(self, graph):
        for key, value in graph.iteritems():
            if key != 'blocks':
                setattr(self, key, graph[key])

        self._id = to_object_id(self._id)

        self.blocks = []
        for block in graph['blocks']:
            block_obj = Block()
            block_obj.load_from_dict(block)
            self.blocks.append(block_obj)

        self._dirty = False

    def __str__(self):
        return 'Graph(_id="{}", blocks={})'.format(self._id, [str(b) for b in self.blocks])

    def __repr__(self):
        return 'Graph(_id="{}", title="{}", blocks={})'.format(self._id, self.title, str(self.blocks))

    def __getattr__(self, name):
        raise Exception("Can't get attribute '{}'".format(name))


if __name__ == "__main__":
    graph = Graph()
    graph.title = "Test graph"
    graph.description = "Test description"

    block_id = db.blocks.find_one({'base_block_name': 'get_resource'})['_id']
    get_resource = Block(block_id)
    get_resource.parameters['resource_id'] = 'Piton.txt'
    get_resource.derived_from = block_id

    block_id = db.blocks.find_one({'base_block_name': 'echo'})['_id']
    echo = Block(block_id)
    echo.parameters['text'] = 'hello world'
    echo.derived_from = block_id

    block_id = db.blocks.find_one({'base_block_name': 'grep'})['_id']
    grep = Block(block_id)
    grep.inputs = {'in': {'block_id': get_resource._id, 'resource': 'out'}}
    grep.parameters['text'] = 'def'
    grep.derived_from = block_id

    graph.blocks = [get_resource, echo, grep]
    # graph.graph_running_status = GraphRunningStatus.READY

    #graph.save()

    # graph = Graph('5a28e0640310e9847ce041f0')
    # print graph.blocks[0].title
