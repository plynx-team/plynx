from plynx.db import DBObjectField, DBObject


class InputValue(DBObject):
    """Basic Value of the Input structure."""

    FIELDS = {
        'node_id': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'output_id': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'resource_id': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
    }

    def __str__(self):
        return 'InputValue({}, {})'.format(self.node_id, self.output_id)

    def __repr__(self):
        return 'InputValue({})'.format(str(self.to_dict()))


class Input(DBObject):
    """Basic Input structure."""

    FIELDS = {
        'name': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'file_types': DBObjectField(
            type=str,
            default=list,
            is_list=True,
            ),
        'values': DBObjectField(
            type=InputValue,
            default=list,
            is_list=True,
            ),
        'min_count': DBObjectField(
            type=int,
            default=1,
            is_list=False,
            ),
        'max_count': DBObjectField(
            type=int,
            default=1,
            is_list=False,
            ),
        }

    def __str__(self):
        return 'Input(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Input({})'.format(str(self.to_dict()))
