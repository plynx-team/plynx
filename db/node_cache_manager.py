from . import NodeCache
from utils.common import to_object_id
from utils.db_connector import *
from constants import NodeRunningStatus

class NodeCacheManager(object):
    """
    The Node cache interface.
    The cache is defined by Node's
        - derived_from
        - inputs
        - parameters
    """

    def __init__(self):
        NodeCacheManager._init_index()

    @staticmethod
    def _init_index():
        db.node_cache.create_index('key', name='key_index', background=True)

    @staticmethod
    def get(node, user_id):
        key = NodeCache.generate_key(node, user_id)
        db_node_cache = db.node_cache.find({
            'key': key
            }).sort('insertion_date', -1).limit(1)
        caches = list(db_node_cache)
        if len(caches):
            res = NodeCache()
            res.load_from_dict(caches[0])
            return res
        else:
            return None

    # Demo: remove user_id
    @staticmethod
    def post(node, graph_id, user_id):
        assert node.node_running_status == NodeRunningStatus.SUCCESS, \
            'Only Nodes with status SUCCESS can be cached'
        node_cache = NodeCache(node=node, graph_id=graph_id, user_id=user_id)
        node_cache.save()
