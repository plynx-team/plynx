from plynx.base import hub
from plynx.db.node_collection_manager import NodeCollectionManager


class CollectionHub(hub.BaseHub):
    def __init__(self, collection, operations):
        super(CollectionHub, self).__init__()

        self.node_collection_manager = NodeCollectionManager(collection=collection)
        self.operations = operations

    def search(self, query):
        return self.node_collection_manager.get_db_objects(node_kinds=self.operations, **query._asdict())
