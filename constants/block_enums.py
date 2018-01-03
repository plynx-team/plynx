from enum import Enum

class JobReturnStatus(Enum):
    SUCCESS = 0
    FAILED = 1

class BlockRunningStatus(Enum):
    CREATED = 0
    IN_QUEUE = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4

BLOCK_RUNNING_STATUS_MAP = {
    status.value: status.name for status in BlockRunningStatus
}
