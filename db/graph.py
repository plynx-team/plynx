import datetime
from db.db_object import DBObject
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from common.graph_enums import GraphRunningStatus
from db.block import Block


class Graph(DBObject):
    """
    Basic graph with db interface
    """

    def __init__(self, graph_id=None):
        super(Graph, self).__init__()
        self._id = None
        self.title = None
        self.running_status = GraphRunningStatus.CREATED
        self.blocks = []

        if graph_id:
            self._id = to_object_id(graph_id)
            self.load()

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
                    "update_date": now,
                    "title": self.title,
                    "blocks": [block.to_dict() for block in self.blocks]
                },
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self):
        graph = db.graphs.find_one({'_id': self._id})

        for key, value in graph.iteritems():
            if key != 'blocks':
                setattr(self, key, graph[key])

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

if __name__ == "__main__":
    graph = Graph()
    graph.title = "Test graph"

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

    graph.save()

    # graph = Graph('5a28e0640310e9847ce041f0')
    # print graph.blocks[0].title
