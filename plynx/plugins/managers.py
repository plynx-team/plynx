import logging
import pydoc
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


class _ExecutorManager(object):
    def __init__(self):
        plugins = get_plugins()
        self.executors_map = plugins.executors
        all_executors = set()
        for parent, children in self.executors_map.items():
            all_executors.add(parent)
            for child in children:
                all_executors.add(child)
        self.name_to_class = {
            class_path: pydoc.locate(class_path)
            for class_path in all_executors
        }

        self.executors_info = {
            executor_name: {
                'alias': self.name_to_class[executor_name].ALIAS,
                'is_graph': self.name_to_class[executor_name].IS_GRAPH,
                'children': self.executors_map.get(executor_name, [])
            } for executor_name in all_executors
        }

        logging.info('Executors info: {}'.format(str(self.executors_info)))


resource_manager = _ResourceManager()
executor_manager = _ExecutorManager()
