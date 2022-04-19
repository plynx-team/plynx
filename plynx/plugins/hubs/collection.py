"""Plynx standard Hub based on the database of Operations"""
from typing import Any, Dict

from plynx.base import hub
from plynx.db.node_collection_manager import NodeCollectionManager


class CollectionHub(hub.BaseHub):
    """Plynx standard Hub based on the database of Operations"""
    def __init__(self, collection, operations):
        super().__init__()

        self.node_collection_manager = NodeCollectionManager(collection=collection)
        self.operations = operations

    def search(self, query: hub.Query) -> Dict[str, Any]:
        return self.node_collection_manager.get_db_objects(
            node_kinds=self.operations,
            **query.to_dict(),  # type: ignore
        )
