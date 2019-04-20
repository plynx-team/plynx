import logging
from plynx.utils.config import get_plugins


class _ResourceManager(object):
    def __init__(self):
        self.resources = get_plugins().resources
        self.name_to_resource = {
            resource.NAME: resource
            for resource in self.resources
        }
        self.resources_dict = {
            resource.NAME: resource.to_dict()
            for resource in self.resources
        }
        logging.info('Resources used: {}'.format(str(self.name_to_resource)))
        assert len(self.resources) == len(self.name_to_resource), 'Duplicated resources found'

    def __getitem__(self, resource_name):
        return self.name_to_resource[resource_name]


resource_manager = _ResourceManager()
