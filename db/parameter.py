from constants import ParameterTypes


class ParameterWidget(object):
    def __init__(self, alias):
        self.alias = alias

    def to_dict(self):
        return {
            'alias': self.alias
        }

    @staticmethod
    def create_from_dict(widget_dict):
        return ParameterWidget(widget_dict['alias'])

    def __str__(self):
        return 'ParameterWidget(alias="{}")'.format(self.alias)

    def __repr__(self):
        return 'ParameterWidget({})'.format(str(self.to_dict()))


class Parameter(object):
    def __init__(self,
                 name,
                 parameter_type,
                 value=None,
                 widget=None,
                 mutable_type=True,
                 removable=True,
                 publicable=True
                 ):
        assert isinstance(name, basestring)
        assert isinstance(parameter_type, basestring)
        assert widget is None or isinstance(widget, ParameterWidget)
        assert type(mutable_type) is bool
        assert type(publicable) is bool
        assert type(removable) is bool
        self.name = name
        self.parameter_type = parameter_type
        self.mutable_type = mutable_type
        self.publicable = publicable
        self.removable = removable
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
            'mutable_type': self.mutable_type,
            'removable': self.removable,
            'publicable': self.publicable,
            'widget': self.widget.to_dict() if self.widget else None
        }

    @staticmethod
    def create_from_dict(parameter_dict):
        if parameter_dict['widget']:
            widget = ParameterWidget.create_from_dict(parameter_dict['widget'])
        else:
            widget = None

        return Parameter(
            name = parameter_dict['name'],
            parameter_type = parameter_dict['parameter_type'],
            value = parameter_dict['value'],
            mutable_type = parameter_dict.get('mutable_type', True),
            publicable = parameter_dict.get('publicable', True),
            removable = parameter_dict.get('removable', True),
            widget = widget
            )

    def __str__(self):
        return 'Parameter(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Parameter({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(Parameter, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))
