class ParameterEnum(object):
    def __init__(self, values=None, index=-1):
        values = values or []
        self.values = values
        self.index = index

    def to_dict(self):
        return {
            'values': self.values,
            'index': self.index
        }

    @classmethod
    def create_from_dict(cls, obj_dict):
        parameter_enum = cls()
        for key, value in obj_dict.iteritems():
            setattr(parameter_enum, key, value)
        return parameter_enum

    def __repr__(self):
        return 'ParameterEnum({})'.format(str(self.to_dict()))


class ParameterCode(object):
    MODES = {'python'}

    def __init__(self, value='', mode='python'):
        self.value = value
        self.mode = mode

    def to_dict(self):
        return {
            'value': self.value,
            'mode': self.mode
        }

    @classmethod
    def create_from_dict(cls, obj_dict):
        parameter_code = cls()
        for key, value in obj_dict.iteritems():
            setattr(parameter_code, key, value)
        return parameter_code

    def __repr__(self):
        return 'ParameterCode({})'.format(str(self.to_dict()))


class ParameterTypes:
    STR = 'str'
    INT = 'int'
    BOOL = 'bool'
    TEXT = 'text'
    ENUM = 'enum'
    LIST_STR = 'list_str'
    LIST_INT = 'list_int'
    CODE = 'code'

    @staticmethod
    def get_default_by_type(parameter_type):
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

    @staticmethod
    def value_is_valid(value, parameter_type):
        if parameter_type == ParameterTypes.STR:
            return isinstance(value, basestring)
        if parameter_type == ParameterTypes.INT:
            try:
                tmp = int(value)
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
            return isinstance(value, list) and all(ParameterTypes.value_is_valid(x, ParameterTypes.STR) for x in value)
        if parameter_type == ParameterTypes.LIST_INT:
            return isinstance(value, list) and all(ParameterTypes.value_is_valid(x, ParameterTypes.INT) for x in value)
        if parameter_type == ParameterTypes.CODE:
            return isinstance(value, ParameterCode)
        else:
            return False
