"""Worker State DB Object and utils"""

from dataclasses import dataclass, field
from typing import List

from dataclasses_json import dataclass_json

from plynx.constants import Collections
from plynx.db.db_object import DBObject
from plynx.db.node import Node
from plynx.utils.common import ObjectId
from plynx.utils.db_connector import get_db_connector


@dataclass_json
@dataclass
class WorkerState(DBObject):
    """Worker statistics snapshot."""
    DB_COLLECTION = Collections.WORKER_STATE

    _id: ObjectId = field(default_factory=ObjectId)
    worker_id: str = ""
    host: str = ""
    runs: List[Node] = field(default_factory=list)
    kinds: List[str] = field(default_factory=list)


def get_worker_states() -> List[WorkerState]:
    """Get all of the workers with latest states"""
    states = getattr(get_db_connector(), Collections.WORKER_STATE).find({}).sort('insertion_date', -1)

    unique_worker_states = {}
    for state_dict in states:
        if state_dict['worker_id'] in unique_worker_states:
            continue
        unique_worker_states[state_dict['worker_id']] = WorkerState.from_dict(state_dict)

    return list(sorted(unique_worker_states.values(), key=lambda state: state.worker_id))
