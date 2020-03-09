import logging
import pydoc
from plynx.utils.config import get_plugins


def _isinstance_namedtuple(x):
    return isinstance(x, tuple) and getattr(x, '_fields', None) is not None


def _as_dict(obj):
    if _isinstance_namedtuple(obj):
        return {
            key: _as_dict(getattr(obj, key)) for key in obj._fields
        }
    elif isinstance(obj, list):
        return [_as_dict(value) for value in obj]
    return obj


class _ResourceManager(object):
    def __init__(self, plugins):
        self.resources = plugins.resources
        self.kind_to_resource_class = {
            resource.kind: pydoc.locate(resource.cls) for resource in self.resources
        }
        self.kind_to_resource_dict = {
            resource.kind: resource._asdict() for resource in self.resources
        }


class _ExecutorManager(object):
    def __init__(self, plugins):
        self.kind_to_executor_class = {}
        self.kind_to_children_kinds = {}
        for o_or_w in plugins.workflows + plugins.operations + plugins.dummy_operations:
            self.kind_to_executor_class[o_or_w.kind] = pydoc.locate(o_or_w.executor)
            if not self.kind_to_executor_class[o_or_w.kind]:
                raise Exception('Executor `{}` not found'.format(o_or_w.executor))
            self.kind_to_children_kinds[o_or_w.kind] = o_or_w.operations

        self.kind_info = {}
        for kind, executor_class in self.kind_to_executor_class.items():
            logging.warning("Initializing executor `{}`".format(kind))
            self.kind_info[kind] = {
                'is_graph': executor_class.IS_GRAPH,
                'children': self.kind_to_children_kinds[kind]
            }


class _OperationManager(object):
    def __init__(self, plugins):
        self.operations = plugins.operations
        self.kind_to_operation_dict = {
            operation.kind: _as_dict(operation) for operation in self.operations
        }


class _HubManager(object):
    def __init__(self, plugins):
        self.hubs = plugins.hubs
        self.kind_to_hub_class = {
            hub.kind: pydoc.locate(hub.cls)(**hub.args) for hub in self.hubs
        }
        self.kind_to_hub_dict = {
            hub.kind: hub._asdict() for hub in self.hubs
        }


class _WorkflowManager(object):
    def __init__(self, plugins):
        self.workflows = plugins.workflows
        self.kind_to_workflow_dict = {
            workflow.kind: workflow._asdict() for workflow in self.workflows
        }


_plugins = get_plugins()

_resource_manager = None
_operation_manager = None
_hub_manager = None
_workflow_manager = None
_executor_manager = None


def get_resource_manager():
    global _resource_manager
    if not _resource_manager:
        _resource_manager = _ResourceManager(_plugins)
    return _resource_manager


def get_operation_manager():
    global _operation_manager
    if not _operation_manager:
        _operation_manager = _OperationManager(_plugins)
    return _operation_manager


def get_hub_manager():
    global _hub_manager
    if not _hub_manager:
        _hub_manager = _HubManager(_plugins)
    return _hub_manager


def get_workflow_manager():
    global _workflow_manager
    if not _workflow_manager:
        _workflow_manager = _WorkflowManager(_plugins)
    return _workflow_manager


def get_executor_manager():
    global _executor_manager
    if not _executor_manager:
        _executor_manager = _ExecutorManager(_plugins)
    return _executor_manager
