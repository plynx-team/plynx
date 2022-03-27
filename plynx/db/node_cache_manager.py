"""Cache Manager and utils."""
import datetime
import logging
from typing import Any, Dict, List, Optional, Union

from plynx.constants import NodeRunningStatus
from plynx.db.node import Node
from plynx.db.node_cache import NodeCache
from plynx.utils.common import ObjectId
from plynx.utils.db_connector import get_db_connector


class NodeCacheManager:
    """The Node cache interface.

    The cache is defined by Node's
        - original_node_id
        - inputs
        - parameters
    """

    @staticmethod
    def get(node: Node) -> Optional[NodeCache]:
        """Pull NodeCache if exists.

        Args:
            node        (Node):             Node object

        Return:
            (NodeCache)     NodeCache or None
        """
        key = NodeCache.generate_key(node)
        db_node_cache = get_db_connector().node_cache.find({
            'key': key,
            'removed': {'$ne': True}
        }).sort('insertion_date', -1).limit(1)
        caches = list(db_node_cache)
        if len(caches) > 0:
            return NodeCache.from_dict(caches[0])
        else:
            return None

    @staticmethod
    def post(node: Node, run_id: ObjectId) -> bool:
        """Create NodeCache instance in the database.

        Args:
            node        (Node):             Node object
            run_id      (ObjectId, str):    Run ID

        Return:
            True if cache saved else False
        """
        assert node.node_running_status == NodeRunningStatus.SUCCESS, \
            'Only Nodes with status SUCCESS can be cached'
        node_cache = NodeCache.instantiate(node=node, run_id=run_id)
        try:
            node_cache.save()
        except Exception as e:  # pylint: disable=broad-except
            logging.error(f"Could not save cache: `{e}`")
            return False
        return True

    @staticmethod
    def _make_query(
            start_datetime: Optional[datetime.datetime] = None,
            end_datetime: Optional[datetime.datetime] = None,
            non_protected_only: bool = False,
            ) -> Dict[str, Any]:
        """Make sample query.

        Args:
            start_datetime  (datetime, None):   Start datetime or None if selecting from beginning
            end_datetime    (datetime, None):   End datetime or None if selecting until now

        Return:
            Iterator on the list of dict-like objects
        """
        and_query: List[Dict[str, Dict[str, Union[bool, datetime.datetime]]]] = []

        insertion_query: Dict[str, Union[bool, datetime.datetime]] = {}
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
    def get_list(
            start_datetime: Optional[datetime.datetime] = None,
            end_datetime: Optional[datetime.datetime] = None,
            non_protected_only: bool = False
            ):
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
