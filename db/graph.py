import datetime
from db.db_object import DBObject
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from db.block import Block


class Graph(DBObject):
    """
    Basic graph with db interface
    """

    def __init__(self, graph_id=None):
        super(Graph, self).__init__()
        self._id = None
        self.title = None
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
        for block in db.blocks.find({'graph_id': self._id}):
            block_obj = Block()
            block_obj.load_from_dict(block)
            self.blocks.append(block_obj)
        print self.blocks

        self._dirty = False


if __name__ == "__main__":
    graph = Graph()
    graph.title = "Test graph"

    get_resource = Block()
    get_resource.title = "Get resource"
    get_resource.base_block_name = "get_resource"
    get_resource.outputs = {'out': ''}
    get_resource.description = 'Get resource'
    get_resource.parameters['resource_id'] = 'Piton.txt'
    get_resource.derived_from = db.blocks.find_one({'base_block_name': get_resource.base_block_name})['_id']

    echo = Block()
    echo.title = "Echo"
    echo.base_block_name = "echo"
    echo.outputs = {'out': ''}
    echo.description = 'Echo block'
    echo.parameters['text'] = 'hello world'
    echo.derived_from = db.blocks.find_one({'base_block_name': echo.base_block_name})['_id']

    grep = Block()
    grep.title = "Grep"
    grep.base_block_name = "grep"
    grep.inputs = {'in': {'block_id': get_resource._id, 'resource': 'out'}}
    grep.outputs = {'out': ''}
    grep.description = 'Grep block'
    grep.parameters['text'] = 'hello world'
    grep.derived_from = db.blocks.find_one({'base_block_name': grep.base_block_name})['_id']

    graph.blocks = [get_resource, echo, grep]

    graph.save()

    #graph = Graph('5a28e0640310e9847ce041f0')
    #print graph.blocks[0].title
