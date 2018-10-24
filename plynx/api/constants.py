class _NodeRunningStatus(object):
    STATIC = 'STATIC'
    CREATED = 'CREATED'
    IN_QUEUE = 'IN_QUEUE'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class _GraphRunningStatus(object):
    CREATED = 'CREATED'
    READY = 'READY'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class _GraphPostAction(object):
    SAVE = 'SAVE'
    APPROVE = 'APPROVE'
    VALIDATE = 'VALIDATE'
    AUTO_LAYOUT = 'AUTO_LAYOUT'


class _GraphPostStatus(object):
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    VALIDATION_FAILED = 'VALIDATION_FAILED'


class _ValidationCode(object):
    IN_DEPENDENTS = 'IN_DEPENDENTS'
    MISSING_INPUT = 'MISSING_INPUT'
    MISSING_PARAMETER = 'MISSING_PARAMETER'
    INVALID_VALUE = 'INVALID_VALUE'
