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

    def __str__(self):
        return 'ParameterWidget(alias="{}")'.format(self.alias)

    def __repr__(self):
        return 'ParameterWidget({})'.format(str(self.to_dict()))


class Parameter(object):
    def __init__(self, name, parameter_type, value=None, widget=None):
        assert isinstance(name, basestring)
        assert isinstance(parameter_type, basestring)
        assert widget is None or isinstance(widget, ParameterWidget)
        self.name = name
        self.parameter_type = parameter_type
        if value is None:
            self.value = ParameterTypes.get_default_by_type(self.parameter_type)
        else:
            self.value = value
        assert ParameterTypes.value_is_valid(self.value, self.parameter_type)
        self.widget = widget

    def to_dict(self):
        return {
            'name': self.name,
            'parameter_type': self.parameter_type,
            'value': self.value,
            'widget': self.widget.to_dict() if self.widget else None
        }

    def load_from_dict(self, parameter_dict):
        if parameter_dict['widget']:
            widget = ParameterWidget()
            widget.load_from_dict(parameter_dict['widget'])
        else:
            widget = None

        self.__init__(
            name = parameter_dict['name'],
            parameter_type = parameter_dict['parameter_type'],
            value = parameter_dict['value'],
            widget = widget
            )

    def __str__(self):
        return 'Parameter(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Parameter({})'.format(str(self.to_dict()))
