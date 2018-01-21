from constants import FileTypes


class Output(object):
    def __init__(self, name, file_type, resource_id=None):
        assert isinstance(name, basestring)
        assert isinstance(file_type, basestring)
        assert isinstance(resource_id, basestring) or resource_id is None
        self.name = name
        self.file_type = file_type
        self.resource_id = resource_id

    def to_dict(self):
        return {
            'name': self.name,
            'file_type': self.file_type,
            'resource_id': self.resource_id
        }

    def load_from_dict(self, output_dict):
        self.__init__(output_dict['name'], output_dict['file_type'], output_dict['file_type'])

    def __str__(self):
        return 'Output(name="{}")'.format(self.name)

    def __repr__(self):
        return 'Output({})'.format(str(self.to_dict()))
