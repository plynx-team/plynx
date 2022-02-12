import inspect
import hashlib

from dataclasses import dataclass
from plynx.constants import NodeStatus, NodeRunningStatus, NodeOrigin
from plynx.utils.common import ObjectId


@dataclass
class VersionData:
    unique_name: str
    hash_value: int


def callable_to_version_data(callable):
    hash_value = hashlib.md5(inspect.getsource(callable).encode()).hexdigest()
    filename = inspect.getfile(callable)
    return VersionData(
        unique_name=f"{filename}:{callable.__name__}",
        hash_value=hash_value,
    )


def func_to_dict(func):
    plynx_params = func.plynx_params

    version_data = callable_to_version_data(func)
    return {
        "_id": str(ObjectId()),
        "_type": "Node",
        "title": plynx_params.title,
        "description": plynx_params.description,
        "node_running_status": NodeRunningStatus.CREATED,
        "node_status": NodeStatus.READY,
        "author": None,
        "kind": plynx_params.kind,
        "origin": NodeOrigin.BUILT_IN_HUBS,
        "code_hash": version_data.hash_value,
        "code_function_location": version_data.unique_name,
        "inputs": list(map(lambda item: item.to_dict(), plynx_params.inputs)),
        "outputs": list(map(lambda item: item.to_dict(), plynx_params.outputs)),
        "parameters": list(map(lambda item: item.to_dict(), plynx_params.params)),
        "logs": [],
    }
