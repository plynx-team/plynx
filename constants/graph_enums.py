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
