from plynx.db import DBObjectField, DBObject


class Output(DBObject):
    """Basic Output structure."""

    FIELDS = {
        'name': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'file_type': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'resource_id': DBObjectField(
            type=str,
            default=None,
            is_list=False,
            ),
    }

    def __str__(self):
        return 'Output(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Output({})'.format(str(self.to_dict()))
