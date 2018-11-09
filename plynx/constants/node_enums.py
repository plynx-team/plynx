class JobReturnStatus:
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'


class NodeRunningStatus:
    STATIC = 'STATIC'
    CREATED = 'CREATED'
    IN_QUEUE = 'IN_QUEUE'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    RESTORED = 'RESTORED'
    FAILED = 'FAILED'
    CANCELED = 'CANCELED'

    _FINISHED_STATUSES = {
        STATIC,
        SUCCESS,
        RESTORED,
        FAILED,
        CANCELED,
    }

    @staticmethod
    def is_finished(node_running_status):
        return node_running_status in NodeRunningStatus._FINISHED_STATUSES


class NodeStatus:
    CREATED = 'CREATED'
    READY = 'READY'
    DEPRECATED = 'DEPRECATED'
    MANDATORY_DEPRECATED = 'MANDATORY_DEPRECATED'


class NodePostAction:
    SAVE = 'SAVE'
    APPROVE = 'APPROVE'
    VALIDATE = 'VALIDATE'
    DEPRECATE = 'DEPRECATE'
    MANDATORY_DEPRECATE = 'MANDATORY_DEPRECATE'
    PREVIEW_CMD = 'PREVIEW_CMD'


class NodePostStatus:
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    VALIDATION_FAILED = 'VALIDATION_FAILED'
