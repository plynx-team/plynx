class GraphRunningStatus:
    CREATED = 'CREATED'
    READY = 'READY'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    CANCELED = 'CANCELED'
    FAILED_WAITING = 'FAILED_WAITING'

    _FAILED_STATUSES = {
        FAILED,
        FAILED_WAITING,
    }

    @staticmethod
    def is_failed(graph_running_status):
        return graph_running_status in GraphRunningStatus._FAILED_STATUSES


class GraphPostAction:
    SAVE = 'SAVE'
    APPROVE = 'APPROVE'
    VALIDATE = 'VALIDATE'
    AUTO_LAYOUT = 'AUTO_LAYOUT'
    UPGRADE_NODES = 'UPGRADE_NODES'
    CANCEL = 'CANCEL'


class GraphPostStatus:
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    VALIDATION_FAILED = 'VALIDATION_FAILED'
