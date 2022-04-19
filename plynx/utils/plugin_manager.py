"""Utils that materialize plugins"""
# pylint: disable=global-statement
import logging
import pydoc
from typing import Any, Dict

from plynx.base.executor import BaseExecutor
from plynx.base.hub import BaseHub
from plynx.base.resource import BaseResource
from plynx.utils.config import PluginsConfig, get_plugins


def _isinstance_namedtuple(x: Any) -> bool:
    return isinstance(x, tuple) and getattr(x, '_fields', None) is not None


def _as_dict(obj: Any):
    if _isinstance_namedtuple(obj):
        return {
            key: _as_dict(getattr(obj, key)) for key in obj._fields
        }
    elif isinstance(obj, list):
        return [_as_dict(value) for value in obj]
    return obj


class _ResourceManager:
    def __init__(self, plugins: PluginsConfig):
        self.resources = plugins.resources
        self.kind_to_resource_class: Dict[str, BaseResource] = {
            resource.kind: pydoc.locate(resource.cls)   # type: ignore
            for resource in self.resources
        }
        self.kind_to_resource_dict: Dict[str, Dict[str, Any]] = {
            resource.kind: resource._asdict() for resource in self.resources
        }
        for kind, resource_class in self.kind_to_resource_class.items():
            self.kind_to_resource_dict[kind]['display_raw'] = resource_class.DISPLAY_RAW


class _ExecutorManager:
    def __init__(self, plugins: PluginsConfig):
        self.kind_to_executor_class: Dict[str, BaseExecutor] = {}
        self.kind_to_icon = {}
        self.kind_to_color = {}
        self.kind_to_title = {}
        for o_or_w in plugins.workflows + plugins.operations + plugins.dummy_operations:
            self.kind_to_executor_class[o_or_w.kind] = pydoc.locate(o_or_w.executor)    # type: ignore
            if not self.kind_to_executor_class[o_or_w.kind]:
                raise Exception(f"Executor `{o_or_w.executor}` not found")
            self.kind_to_icon[o_or_w.kind] = o_or_w.icon
            self.kind_to_color[o_or_w.kind] = o_or_w.color
            self.kind_to_title[o_or_w.kind] = o_or_w.title

        self.kind_info = {}
        for kind, executor_class in self.kind_to_executor_class.items():
            logging.info(f"Initializing executor `{kind}`")
            self.kind_info[kind] = {
                'is_graph': executor_class.IS_GRAPH,
                'title': self.kind_to_title[kind],
                'icon': self.kind_to_icon[kind],
                'color': self.kind_to_color[kind],
            }


class _OperationManager:
    def __init__(self, plugins: PluginsConfig):
        self.operations = plugins.operations
        self.kind_to_operation_dict = {
            operation.kind: _as_dict(operation) for operation in self.operations
        }


class _HubManager:
    def __init__(self, plugins: PluginsConfig):
        self.hubs = plugins.hubs
        self.kind_to_hub_class: Dict[str, BaseHub] = {
            hub.kind: pydoc.locate(hub.cls)(**hub.args)     # type: ignore
            for hub in self.hubs
        }
        self.kind_to_hub_dict = {
            hub.kind: hub._asdict() for hub in self.hubs
        }


class _WorkflowManager:
    def __init__(self, plugins: PluginsConfig):
        self.workflows = plugins.workflows
        self.kind_to_workflow_dict = {
            workflow.kind: workflow._asdict() for workflow in self.workflows
        }


_plugins: PluginsConfig = get_plugins()

_RESOURCE_MANAGER = None
_OPERATION_MANAGER = None
_HUB_MANAGER = None
_WORKFLOW_MANAGER = None
_EXECUTOR_MANAGER = None

_PLUGINS_DICT = None


def get_resource_manager():
    """Generate Resource plugin structure"""
    global _RESOURCE_MANAGER
    if not _RESOURCE_MANAGER:
        _RESOURCE_MANAGER = _ResourceManager(_plugins)
    return _RESOURCE_MANAGER


def get_operation_manager():
    """Generate Operation plugin structure"""
    global _OPERATION_MANAGER
    if not _OPERATION_MANAGER:
        _OPERATION_MANAGER = _OperationManager(_plugins)
    return _OPERATION_MANAGER


def get_hub_manager():
    """Generate Hub plugin structure"""
    global _HUB_MANAGER
    if not _HUB_MANAGER:
        _HUB_MANAGER = _HubManager(_plugins)
    return _HUB_MANAGER


def get_workflow_manager():
    """Generate Workflow plugin structure"""
    global _WORKFLOW_MANAGER
    if not _WORKFLOW_MANAGER:
        _WORKFLOW_MANAGER = _WorkflowManager(_plugins)
    return _WORKFLOW_MANAGER


def get_executor_manager():
    """Generate Exectutor plugin structure"""
    global _EXECUTOR_MANAGER
    if not _EXECUTOR_MANAGER:
        _EXECUTOR_MANAGER = _ExecutorManager(_plugins)
    return _EXECUTOR_MANAGER


def get_plugins_dict():
    """Generate all of the plugins structure"""
    global _PLUGINS_DICT
    if not _PLUGINS_DICT:
        _PLUGINS_DICT = {
            'resources_dict': get_resource_manager().kind_to_resource_dict,
            'operations_dict': get_operation_manager().kind_to_operation_dict,
            'hubs_dict': get_hub_manager().kind_to_hub_dict,
            'workflows_dict': get_workflow_manager().kind_to_workflow_dict,
            'executors_info': get_executor_manager().kind_info,
        }
    return _PLUGINS_DICT
