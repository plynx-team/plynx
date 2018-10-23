class GraphRunningStatus(object):
    CREATED = 'CREATED'
    READY = 'READY'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    CANCELED = 'CANCELED'


class GraphPostAction:
    SAVE = 'SAVE'
    APPROVE = 'APPROVE'
    VALIDATE = 'VALIDATE'
    AUTO_LAYOUT = 'AUTO_LAYOUT'
    UPDATE_NODES = 'UPDATE_NODES'
    CANCEL = 'CANCEL'


class GraphPostStatus(object):
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    VALIDATION_FAILED = 'VALIDATION_FAILED'
