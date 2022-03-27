"""Cancelation DB Object and utils"""
from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_json import dataclass_json

from plynx.constants import Collections
from plynx.db.db_object import DBObject
from plynx.utils.common import ObjectId
from plynx.utils.db_connector import get_db_connector


@dataclass_json
@dataclass
class RunCancellation(DBObject):
    """RunCancellation represents Run Cancellation event in the database."""
    DB_COLLECTION = Collections.RUN_CANCELLATIONS

    _id: ObjectId = field(default_factory=ObjectId)
    run_id: Optional[ObjectId] = None


class RunCancellationManager:
    """RunCancellationManager contains basic operations related to `runs_cancellations` collection."""

    run_id: ObjectId

    @staticmethod
    def cancel_run(run_id: ObjectId):
        """Cancel Run.
        Args:
            run_id    (ObjectId) RunID
        """
        run_cancellation = RunCancellation(
            run_id=run_id,
        )
        run_cancellation.save()
        return True

    @staticmethod
    def get_run_cancellations() -> List[RunCancellation]:
        """Get all Run Cancellation events"""
        res = []
        for runs_cancellation_dict in get_db_connector()[Collections.RUN_CANCELLATIONS].find():
            res.append(
                RunCancellation.from_dict(runs_cancellation_dict)
            )
        return res

    @staticmethod
    def remove(runs_cancellation_ids: List[ObjectId]):
        """Remove Run Cancellation events with given Ids
        Args:
            runs_cancellation_ids     (list of ObjectID)  List of Run IDs to remove
        """
        get_db_connector()[Collections.RUN_CANCELLATIONS].delete_many({'_id': {'$in': runs_cancellation_ids}})
