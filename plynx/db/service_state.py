from plynx.constants import Collections
from plynx.db import DBObjectField, DBObject, Node
from plynx.utils.db_connector import get_db_connector
from plynx.utils.common import ObjectId


class WorkerState(DBObject):
    """Status of the worker"""
    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        'worker_id': DBObjectField(
            type=str,
            default=None,
            is_list=False,
            ),
        'graph_id': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'node': DBObjectField(
            type=Node,
            default=None,
            is_list=False,
            ),
        'host': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'num_finished_jobs': DBObjectField(
            type=int,
            default=0,
            is_list=False,
            ),
    }


class MasterState(DBObject):
    """Master statistics snapshot."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        'workers': DBObjectField(
            type=WorkerState,
            default=list,
            is_list=True,
            ),
    }

    DB_COLLECTION = Collections.MASTER_STATE


def get_master_state():
    states = getattr(get_db_connector(), MasterState.DB_COLLECTION)\
           .find({}).sort('insertion_date', -1).limit(1)
    return states[0] if states.count() > 0 else None
