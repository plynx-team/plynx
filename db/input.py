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
        res = {
            'block_id': block_id,
            'output_id': output_id,
            'resource_id': resource_id            
        }

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

    def load_from_dict(self, input_dict):
        self.__init__(input_dict['name'], input_dict['file_types'])
        self.values = []
        for value_dict in input_dict['values']:
            input_value = InputValue(
                value_dict.get('block_id', None),
                value_dict.get('output_id', None),
                value_dict.get('resource_id', None)
                )
            self.values.append(input_value)
