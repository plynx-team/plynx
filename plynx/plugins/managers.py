import logging
import pydoc
from plynx.utils.config import get_plugins


_plugins = get_plugins()


class _ResourceManager(object):
    def __init__(self):
        self.resources = _plugins.resources
        self.kind_to_resource_cls = {
            resource_kind: pydoc.locate(resource_kind)
            for resource_kind in self.resources
        }
        self.kind_to_resource_dict = {
            resource_kind: cls.to_dict()
            for resource_kind, cls in self.kind_to_resource_cls.items()
        }
        logging.info('Resources used: {}'.format(str(self.kind_to_resource_dict)))

    def __getitem__(self, resource_kind):
        return self.kind_to_resource[resource_kind]


class _ExecutorManager(object):
    def __init__(self):
        self.kind_to_executor_class = {}
        self.kind_to_children_kinds = {}
        for o_or_w in _plugins.workflows + _plugins.operations:
            self.kind_to_executor_class[o_or_w.kind] = pydoc.locate(o_or_w.executor)
            self.kind_to_children_kinds[o_or_w.kind] = o_or_w.operations

        self.kind_info = {
            kind: {
                'alias': executor_class.ALIAS,
                'is_graph': executor_class.IS_GRAPH,
                'children': self.kind_to_children_kinds[kind]
            } for kind, executor_class in self.kind_to_executor_class.items()
        }

        logging.info('Executors info: {}'.format(str(self.kind_info)))


#resource_manager = _ResourceManager()
"""
'plugins_dict': {
    'resources_dict': resource_manager.resources_dict,
    'executors_info': executor_manager.executors_info,
},
"""
class _OperationManager(object):
    def __init__(self):
        self.operations = _plugins.operations
        self.kind_to_operation = {
            operation.kind: operation._asdict() for operation in self.operations
        }

    def __getitem__(self, operation_kind):
        return self.kind_to_operation[operation_kind]


class _WorkflowManager(object):
    def __init__(self):
        self.kind_to_workflow = _plugins.workflows
        self.workflows = _plugins.workflows
        self.kind_to_workflow = {
            workflow.kind: workflow._asdict() for workflow in self.workflows
        }

    def __getitem__(self, resource_kind):
        return self.kind_to_workflow[resource_kind]

resource_manager = _ResourceManager()
operation_manager = _OperationManager()
workflow_manager = _WorkflowManager()
executor_manager = _ExecutorManager()
