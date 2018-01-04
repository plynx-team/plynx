from enum import Enum


class GraphRunningStatus(Enum):
    CREATED = 0
    READY = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4

GRAPH_RUNNING_STATUS_MAP = {
    status.value: status.name for status in GraphRunningStatus
}

GRAPH_RUNNING_STATUS_STR_MAP = {
    status.name: status.value for status in GraphRunningStatus
}

def to_graph_running_status(graph_running_status):
    if isinstance(graph_running_status, int):
        return GraphRunningStatus(graph_running_status)
    if isinstance(graph_running_status, basestring):
        return GraphRunningStatus(GRAPH_RUNNING_STATUS_STR_MAP[graph_running_status.upper()])
    else:
        return graph_running_status
