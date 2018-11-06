from . import NodeCache
from plynx.utils.common import to_object_id
from plynx.utils.db_connector import *
from plynx.constants import NodeRunningStatus


class NodeCacheManager(object):
    """The Node cache interface.

    The cache is defined by Node's
        - parent_node
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
        """Pull NodeCache if exists.

        Args:
            node        (Node):             Node object
            user_id     (ObjectId, str):    User ID

        Return:
            (NodeCache)     NodeCache or None
        """
        key = NodeCache.generate_key(node, user_id)
        db_node_cache = db.node_cache.find({
            'key': key
        }).sort('insertion_date', -1).limit(1)
        caches = list(db_node_cache)
        if len(caches):
            return NodeCache.from_dict(caches[0])
        else:
            return None

    # TODO Demo: remove user_id
    @staticmethod
    def post(node, graph_id, user_id):
        """Create NodeCache instance in the database.

        Args:
            node        (Node):             Node object
            graph_id    (ObjectId, str):    Graph ID
            user_id     (ObjectId, str):    User ID
        """
        assert node.node_running_status == NodeRunningStatus.SUCCESS, \
            'Only Nodes with status SUCCESS can be cached'
        node_cache = NodeCache.instantiate(node=node, graph_id=graph_id, user_id=user_id)
        node_cache.save()
