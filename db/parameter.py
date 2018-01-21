from constants import ParameterTypes


class ParameterWidget(object):
    def __init__(self, alias):
        self.alias = alias

    def to_dict(self):
        return {
            'alias': self.alias
        }

    def load_from_dict(self, widget_dict):
        self.__init__(widget_dict['alias'])


class Parameter(object):
    def __init__(self, name, parameter_type, value=None, is_public=True):
        assert isinstance(name, basestring)
        assert isinstance(parameter_type, basestring)
        assert isinstance(resource_id, basestring) or resource_id is None
        self.name = name
        self.parameter_type = parameter_type
        if value is None:
            self.value = ParameterTypes.get_default_by_type(parameter_type)
        else:
            self.value = value
        self.is_public = is_public

    def to_dict(self):
        return {
            'name': self.name,
            'parameter_type': self.parameter_type,
            'value': self.value,
            'is_public': self.is_public
        }

    def load_from_dict(self, parameter_dict):
        self.__init__(
            name = parameter_dict['name'],
            parameter_type = parameter_dict['parameter_type'],
            value = parameter_dict['value'],
            is_public = parameter_dict['is_public']
            )
