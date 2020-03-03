from plynx.constants import Collections
from plynx.db.db_object import DBObject, DBObjectField
from plynx.db.node import Node
from plynx.utils.db_connector import get_db_connector
from plynx.utils.common import ObjectId


class WorkerState(DBObject):
    """Worker statistics snapshot."""

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
        'host': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'runs': DBObjectField(
            type=Node,
            default=list,
            is_list=True,
            ),
        'kinds': DBObjectField(
            type=str,
            default=list,
            is_list=True,
            ),
    }

    DB_COLLECTION = Collections.WORKER_STATE


def get_worker_states():
    states = getattr(get_db_connector(), Collections.WORKER_STATE)\
           .find({}).sort('insertion_date', -1)

    unique_worker_states = {}
    for state in states:
        if state['worker_id'] in unique_worker_states:
            continue
        unique_worker_states[state['worker_id']] = state

    return list(sorted(unique_worker_states.values(), key=lambda state: state['worker_id']))
