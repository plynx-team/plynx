from plynx.constants import FileTypes


class InputValue(object):
    def __init__(self, node_id, output_id, resource_id):
        assert isinstance(node_id, basestring)
        assert isinstance(output_id, basestring)
        assert isinstance(resource_id, basestring) or resource_id is None
        self.node_id = node_id
        self.output_id = output_id
        self.resource_id = resource_id

    def to_dict(self):
        return {
            'node_id': self.node_id,
            'output_id': self.output_id,
            'resource_id': self.resource_id
        }

    def __str__(self):
        return 'InputValue({}, {})'.format(self.node_id, self.output_id)

    def __repr__(self):
        return 'InputValue({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(InputValue, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))


class Input(object):
    PROPERTIES = ['values']

    def __init__(self, values=None):
        self.name = ''
        self.file_types = []
        if values is None:
            values = []
        self.values = values
        self.min_count = 1
        self.max_count = 1

    def to_dict(self):
        return {
            'name': self.name,
            'file_types': self.file_types,
            'values': [value.to_dict() for value in self.values],
            'min_count': self.min_count,
            'max_count': self.max_count
        }

    @staticmethod
    def create_from_dict(input_dict):
        res = Input()
        for key, value in input_dict.iteritems():
            if key not in Input.PROPERTIES:
                setattr(res, key, value)

        res.values = []
        for value_dict in input_dict['values']:
            input_value = InputValue(
                value_dict.get('node_id', None),
                value_dict.get('output_id', None),
                value_dict.get('resource_id', None)
            )
            res.values.append(input_value)

        assert isinstance(res.name, basestring)
        assert isinstance(res.file_types, list)
        assert isinstance(res.min_count, int)
        assert isinstance(res.max_count, int)
        assert isinstance(res.values, list)
        return res

    def __str__(self):
        return 'Input(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Input({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(Input, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))
