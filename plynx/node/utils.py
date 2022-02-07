from plynx.constants import NodeStatus, NodeRunningStatus
from plynx.utils.common import ObjectId


def func_to_dict(func):
    plynx_params = func.plynx_params
    return {
        "_id": str(ObjectId()),
        "_type": "Node",
        "title": plynx_params.title,
        "description": plynx_params.description,
        "node_running_status": NodeRunningStatus.CREATED,
        "node_status": NodeStatus.READY,
        "author": None,
        "kind": plynx_params.kind,
        "inputs": list(map(lambda item: item.to_dict(), plynx_params.inputs)),
        "outputs": list(map(lambda item: item.to_dict(), plynx_params.outputs)),
        "parameters": list(map(lambda item: item.to_dict(), plynx_params.params)),
        "logs": [],
    }
