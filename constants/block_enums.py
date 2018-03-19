class JobReturnStatus(object):
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class BlockRunningStatus(object):
    STATIC = 'STATIC'
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


class BlockPostAction:
    SAVE = 'SAVE'
    APPROVE = 'APPROVE'
    VALIDATE = 'VALIDATE'
    DEPRECATE = 'DEPRECATE'


class BlockPostStatus(object):
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    VALIDATION_FAILED = 'VALIDATION_FAILED'
