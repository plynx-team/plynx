from plynx.constants import Collections
from plynx.db.db_object import DBObject, DBObjectField
from plynx.utils.common import ObjectId


class Group(DBObject):
    """Group with db interface."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        '_type': DBObjectField(
            type=str,
            default='Group',
            is_list=False,
            ),
        'title': DBObjectField(
            type=str,
            default='Title',
            is_list=False,
            ),
        # Kind, such as plynx.plugins.executors.local.BashJinja2. Derived from from plynx.plugins.executors.BaseExecutor class.
        'kind': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'items': DBObjectField(
            type=lambda x: x,   # Preserve type
            default=list,
            is_list=True,
            ),
        'author': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'starred': DBObjectField(
            type=bool,
            default=False,
            is_list=False,
            ),
    }

    DB_COLLECTION = Collections.GROUPS

    def __str__(self):
        return 'Group(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'Group({})'.format(str(self.to_dict()))
