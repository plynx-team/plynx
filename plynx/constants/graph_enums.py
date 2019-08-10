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
    REARRANGE = 'REARRANGE'
    UPGRADE_NODES = 'UPGRADE_NODES'
    CANCEL = 'CANCEL'
    GENERATE_CODE = 'GENERATE_CODE'
    CLONE = 'CLONE'


class GraphPostStatus:
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    VALIDATION_FAILED = 'VALIDATION_FAILED'


class GraphNodePostAction:
    INSERT_NODE = 'insert_node'
    LIST_NODES = 'list_nodes'
    REMOVE_NODE = 'remove_node'
    CHANGE_PARAMETER = 'change_parameter'
    CREATE_LINK = 'create_link'
    REMOVE_LINK = 'remove_link'
