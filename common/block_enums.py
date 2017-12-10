from enum import Enum

class JobReturnStatus(Enum):
    SUCCESS = 0
    FAILED = 1

class BlockRunningStatus(object):
    CREATED = 0
    IN_QUEUE = 1
    RUNNING = 2
    SUCCESS = 3
    FAILED = 4
