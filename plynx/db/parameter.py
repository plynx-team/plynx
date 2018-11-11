from past.builtins import basestring
from plynx.db import DBObjectField, DBObject
from plynx.constants import ParameterTypes


class ParameterEnum(DBObject):
    """Enum value."""

    FIELDS = {
        'values': DBObjectField(
            type=str,
            default=list,
            is_list=True,
            ),
        'index': DBObjectField(
            type=str,
            default=-1,
            is_list=False,
            ),
    }

    def __repr__(self):
        return 'ParameterEnum({})'.format(str(self.to_dict()))


class ParameterCode(DBObject):
    """Code value."""

    FIELDS = {
        'value': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'mode': DBObjectField(
            type=str,
            default='python',
            is_list=False,
            ),
    }

    # Unused
    MODES = {'python'}

    def __repr__(self):
        return 'ParameterCode({})'.format(str(self.to_dict()))


def _get_default_by_type(parameter_type):
    if parameter_type == ParameterTypes.STR:
        return ''
    if parameter_type == ParameterTypes.INT:
        return 0
    if parameter_type == ParameterTypes.BOOL:
        return False
    if parameter_type == ParameterTypes.TEXT:
        return ''
    if parameter_type == ParameterTypes.ENUM:
        return ParameterEnum()
    if parameter_type == ParameterTypes.LIST_STR:
        return []
    if parameter_type == ParameterTypes.LIST_INT:
        return []
    if parameter_type == ParameterTypes.CODE:
        return ParameterCode()
    else:
        return None


def _value_is_valid(value, parameter_type):
    if parameter_type == ParameterTypes.STR:
        return isinstance(value, basestring)
    if parameter_type == ParameterTypes.INT:
        try:
            int(value)
        except Exception:
            return False
        return True
    if parameter_type == ParameterTypes.BOOL:
        return isinstance(value, int)
    if parameter_type == ParameterTypes.TEXT:
        return isinstance(value, basestring)
    if parameter_type == ParameterTypes.ENUM:
        return isinstance(value, ParameterEnum)
    if parameter_type == ParameterTypes.LIST_STR:
        return isinstance(value, list) and all(_value_is_valid(x, ParameterTypes.STR) for x in value)
    if parameter_type == ParameterTypes.LIST_INT:
        return isinstance(value, list) and all(_value_is_valid(x, ParameterTypes.INT) for x in value)
    if parameter_type == ParameterTypes.CODE:
        return isinstance(value, ParameterCode)
    else:
        return False


# TODO remove Widget
class ParameterWidget(DBObject):
    """Basic ParameterWidget structure."""

    FIELDS = {
        'alias': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
    }

    def __str__(self):
        return 'ParameterWidget(alias="{}")'.format(self.alias)

    def __repr__(self):
        return 'ParameterWidget({})'.format(str(self.to_dict()))


class Parameter(DBObject):
    """Basic Parameter structure."""

    FIELDS = {
        'name': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'parameter_type': DBObjectField(
            type=str,
            default=ParameterTypes.STR,
            is_list=False,
            ),
        # TODO make type factory
        'value': DBObjectField(
            type=lambda x: x,   # Preserve type
            default='',
            is_list=False,
            ),
        'mutable_type': DBObjectField(
            type=bool,
            default=True,
            is_list=False,
            ),
        'removable': DBObjectField(
            type=bool,
            default=True,
            is_list=False,
            ),
        'publicable': DBObjectField(
            type=bool,
            default=True,
            is_list=False,
            ),
        'widget': DBObjectField(
            type=ParameterWidget,
            default=None,
            is_list=False,
            ),
    }

    def __init__(self, obj_dict=None):
        super(Parameter, self).__init__(obj_dict)

        # `value` field is a special case: the type depends on `parameter_type`
        if self.value is None:
            self.value = _get_default_by_type(self.parameter_type)
        elif self.parameter_type == ParameterTypes.ENUM:
            self.value = ParameterEnum.from_dict(self.value)
        elif self.parameter_type == ParameterTypes.CODE:
            self.value = ParameterCode.from_dict(self.value)
        assert _value_is_valid(self.value, self.parameter_type), \
            "Invalid parameter value type: {}: {}".format(self.name, self.value)

    def __str__(self):
        return 'Parameter(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Parameter({})'.format(str(self.to_dict()))
