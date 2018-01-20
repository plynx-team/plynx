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

BLOCK_RUNNING_STATUS_STR_MAP = {
    status.name: status.value for status in BlockRunningStatus
}


def to_block_running_status(block_running_status):
    if isinstance(block_running_status, int):
        return BlockRunningStatus(block_running_status)
    if isinstance(block_running_status, basestring):
        return BlockRunningStatus(BLOCK_RUNNING_STATUS_STR_MAP[block_running_status.upper()])
    else:
        return block_running_status
