from . import BlockCache
from utils.common import to_object_id
from utils.db_connector import *
from constants import BlockRunningStatus

class BlockCacheManager(object):
    """
    The block cache interface.
    The cache is defined by blocks's
        - derived_from
        - inputs
        - parameters
    """

    def __init__(self):
        BlockCacheManager._init_index()

    @staticmethod
    def _init_index():
        db.block_cache.create_index('key', name='key_index', background=True)

    @staticmethod
    def get(block):
        key = BlockCache.generate_key(block)
        db_block_cache = db.block_cache.find({
            'key': key
            }).sort('insertion_date', -1).limit(1)
        caches = list(db_block_cache)
        if len(caches):
            res = BlockCache()
            res.load_from_dict(caches[0])
            return res
        else:
            return None

    @staticmethod
    def post(block, graph_id):
        assert block.block_running_status == BlockRunningStatus.SUCCESS, \
            'Only blocks with status SUCCESS can be cached'
        block_cache = BlockCache(block=block, graph_id=graph_id)
        block_cache.save()
