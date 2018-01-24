from constants import FileTypes


class InputValue(object):
    def __init__(self, block_id, output_id, resource_id):
        assert isinstance(block_id, basestring)
        assert isinstance(output_id, basestring)
        assert isinstance(resource_id, basestring) or resource_id is None
        self.block_id = block_id
        self.output_id = output_id
        self.resource_id = resource_id

    def to_dict(self):
        return {
            'block_id': self.block_id,
            'output_id': self.output_id,
            'resource_id': self.resource_id            
        }

    def __str__(self):
        return 'InputValue({}, {})'.format(self.block_id, self.output_id)

    def __repr__(self):
        return 'InputValue({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(InputValue, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))


class Input(object):
    def __init__(self, name, file_types, values=None):
        assert isinstance(name, basestring)
        assert isinstance(file_types, list)
        self.name = name
        self.file_types = file_types
        if values is None:
            values = []
        assert isinstance(values, list)
        self.values = values

    def to_dict(self):
        return {
            'name': self.name,
            'file_types': self.file_types,
            'values': [value.to_dict() for value in self.values]
        }

    @staticmethod
    def create_from_dict(input_dict):
        res = Input(input_dict['name'], input_dict['file_types'])
        res.values = []
        for value_dict in input_dict['values']:
            input_value = InputValue(
                value_dict.get('block_id', None),
                value_dict.get('output_id', None),
                value_dict.get('resource_id', None)
                )
            res.values.append(input_value)
        return res

    def __str__(self):
        return 'Input(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Input({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(Input, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))