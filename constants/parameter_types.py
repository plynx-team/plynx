class ParameterTypes:
    STR = 'str'

    @staticmethod
    def get_default_by_type(parameter_type):
        if parameter_type == ParameterTypes.STR:
            return ''
        else:
            return None

    @staticmethod
    def value_is_valid(value, parameter_type):
        if parameter_type == ParameterTypes.STR:
            return isinstance(value, basestring)
        else:
            return False
