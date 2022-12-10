"""General PLynx utils for user-defined Operations."""
import hashlib
import inspect
import sys
from dataclasses import dataclass
from typing import Callable, Union

from plynx.constants import NodeOrigin, NodeRunningStatus, NodeStatus
from plynx.utils.common import ObjectId


@dataclass
class VersionData:
    """Internal versioning data structure"""
    unique_name: str
    hash_value: str


@dataclass
class Group:
    """Collection of Operations"""
    title: str
    items: list

    def to_dict(self):
        """Dict representation"""
        return {
            "_id": str(ObjectId()),
            "_type": "Group",
            "title": self.title,
            "items": list(map(func_or_group_to_dict, self.items)),  # pylint: disable=redefined-builtin
        }


def callable_to_version_data(callable_obj: Callable) -> VersionData:
    """Generate versioning token"""
    code = inspect.getsource(callable_obj)
    python_version = f"{sys.version_info.major}-{sys.version_info.minor}"
    hash_object = f"{code}-{python_version}"
    hash_value = hashlib.md5(hash_object.encode()).hexdigest()

    filename = inspect.getfile(callable_obj)
    return VersionData(
        unique_name=f"{filename}:{callable_obj.__name__}",
        hash_value=hash_value,
    )


def func_or_group_to_dict(func_or_group: Union[Callable, Group]):
    """Recursive serializer"""
    if isinstance(func_or_group, Group):
        return func_or_group.to_dict()
    plynx_params = func_or_group.plynx_params   # type: ignore

    version_data = callable_to_version_data(func_or_group)
    return {
        "_id": str(ObjectId()),
        "_type": "Node",
        "title": plynx_params.title,
        "description": plynx_params.description,
        "node_running_status": NodeRunningStatus.CREATED,
        "node_status": NodeStatus.READY,
        "author": None,
        "auto_run_enabled": plynx_params.auto_run_enabled,
        "kind": plynx_params.kind,
        "origin": NodeOrigin.BUILT_IN_HUBS,
        "code_hash": version_data.hash_value,
        "code_function_location": version_data.unique_name,
        "inputs": list(map(lambda item: item.to_dict(), plynx_params.inputs)),
        "outputs": list(map(lambda item: item.to_dict(), plynx_params.outputs)),
        "parameters": list(map(lambda item: item.to_dict(), plynx_params.params)),
        "logs": [],
    }
