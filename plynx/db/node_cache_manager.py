import logging
from plynx.db import NodeCache
from plynx.utils.db_connector import get_db_connector
from plynx.constants import NodeRunningStatus


class NodeCacheManager(object):
    """The Node cache interface.

    The cache is defined by Node's
        - parent_node
        - inputs
        - parameters
    """

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
        db_node_cache = get_db_connector().node_cache.find({
            'key': key,
            'removed': {'$ne': True}
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

        Return:
            True if cache saved else False
        """
        assert node.node_running_status == NodeRunningStatus.SUCCESS, \
            'Only Nodes with status SUCCESS can be cached'
        node_cache = NodeCache.instantiate(node=node, graph_id=graph_id, user_id=user_id)
        try:
            node_cache.save()
        except Exception as e:
            logging.error('Could not save cache: `{}`'.format(e))
            return False
        return True

    @staticmethod
    def _make_query(start_datetime=None, end_datetime=None, non_protected_only=False):
        """Make sample query.

        Args:
            start_datetime  (datetime, None):   Start datetime or None if selecting from beginning
            end_datetime    (datetime, None):   End datetime or None if selecting until now

        Return:
            Iterator on the list of dict-like objects
        """
        and_query = []

        insertion_query = {}
        if start_datetime:
            insertion_query['$gte'] = start_datetime
        if end_datetime:
            insertion_query['$lt'] = end_datetime
        if insertion_query:
            and_query.append({'insertion_date': insertion_query})

        if non_protected_only:
            and_query.append({'protected': {'$ne': True}})

        return {'$and': and_query} if and_query else {}

    @staticmethod
    def get_list(start_datetime=None, end_datetime=None, non_protected_only=False):
        """List of NodeCache objects.

        Args:
            start_datetime  (datetime, None):   Start datetime or None if selecting from beginning
            end_datetime    (datetime, None):   End datetime or None if selecting until now

        Return:
            Iterator on the list of dict-like objects
        """
        return get_db_connector().node_cache.find(NodeCacheManager._make_query(start_datetime, end_datetime, non_protected_only))

    @staticmethod
    def clean_up():
        """Remove NodeCache objects with flag `removed` set
        """
        return get_db_connector().node_cache.remove({'removed': True})
