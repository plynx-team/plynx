from abc import ABCMeta, abstractmethod


class ParameterTypes(object):
    STR = 'str'

    @abstractmethod
    def get_default_by_type(parameter_type):
        if parameter_type == ParameterTypes.STR:
            return ''
        else:
            return None
