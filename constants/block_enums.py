class JobReturnStatus(object):
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class BlockRunningStatus(object):
    CREATED = 'CREATED'
    IN_QUEUE = 'IN_QUEUE'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class BlockStatus(object):
    CREATED = 'CREATED'
    READY = 'READY'
    DEPRECATED = 'DEPRECATED'
    MANDATORY_DEPRECATED = 'MANDATORY_DEPRECATED'