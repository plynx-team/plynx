class ParameterTypes:
    STR = 'str'
    INT = 'int'
    BOOL = 'bool'
    TEXT = 'text'

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
        else:
            return None

    @staticmethod
    def value_is_valid(value, parameter_type):
        if parameter_type == ParameterTypes.STR:
            return isinstance(value, basestring)
        if parameter_type == ParameterTypes.INT:
            try:
                tmp = int(value)
            except:
                return False
            return True
        if parameter_type == ParameterTypes.BOOL:
            return isinstance(value, int)
        if parameter_type == ParameterTypes.TEXT:
            return isinstance(value, basestring)
        else:
            return False
