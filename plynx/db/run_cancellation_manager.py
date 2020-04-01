from plynx.db.db_object import DBObject, DBObjectField
from plynx.constants import Collections
from plynx.utils.common import ObjectId
from plynx.utils.db_connector import get_db_connector


class RunCancellation(DBObject):
    """RunCancellation represents Run Cancellation event in the database."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        "run_id": DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
    }

    DB_COLLECTION = Collections.RUN_CANCELLATIONS


class RunCancellationManager(object):
    """RunCancellationManager contains basic operations related to `runs_cancellations` collection."""

    @staticmethod
    def cancel_run(run_id):
        """Cancel Run.
        Args:
            run_id    (ObjectId, str) RunID
        """
        run_cancellation = RunCancellation()
        run_cancellation.run_id = ObjectId(run_id)
        run_cancellation.save()
        return True

    @staticmethod
    def get_run_cancellations():
        """Get all Run Cancellation events"""
        res = []
        for runs_cancellation_dict in get_db_connector()[Collections.RUN_CANCELLATIONS].find():
            res.append(
                RunCancellation.from_dict(runs_cancellation_dict)
            )
        return res

    @staticmethod
    def remove(runs_cancellation_ids):
        """Remove Run Cancellation events with given Ids
        Args:
            runs_cancellation_ids     (list of ObjectID)  List of Run IDs to remove
        """
        get_db_connector()[Collections.RUN_CANCELLATIONS].delete_many({'_id': {'$in': runs_cancellation_ids}})
