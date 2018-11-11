from plynx.db import DBObject, DBObjectField
from plynx.utils.common import ObjectId


class Feedback(DBObject):
    """Basic Feedback class with db interface."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        "name": DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        "email": DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        "message": DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        "url": DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
    }

    DB_COLLECTION = 'feedback'

    def __str__(self):
        return 'Feedback(_id="{}", user={})'.format(self._id, self.user)

    def __repr__(self):
        return 'User({})'.format(self.to_dict())
