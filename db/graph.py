import datetime
from db.db_object import DBObject
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from db.block import Block


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
    #from graph.base_blocks.collection import BlockCollection
    #col = BlockCollection()
    #block = col.name_to_class['echo']()
    #block.parameters['text'] = ['Hello world']
    #block = db.blocks.find_one({'base_name': 'echo'})
    #del block['name']
    #block.
    #del block['_id']
    block = Block()
    block.title = "Echo"
    block.base_block_name = "echo"
    block.outputs = {'out': ''}
    block.description = 'Echo block'
    block.parameters['text'] = 'hello world'
    block.derived_from = ObjectId("5a2aba980310e99ac1b5b634")

    graph.blocks = [block]
    graph.save()

    #graph.save()
    #graph = Graph('5a28e0640310e9847ce041f0')
    #print graph.blocks[0].title
