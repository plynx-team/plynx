"""Node constants"""
from bson.objectid import ObjectId


class NodeRunningStatus:
    """Running status enum"""
    STATIC = 'STATIC'
    CREATED = 'CREATED'
    READY = 'READY'
    IN_QUEUE = 'IN_QUEUE'
    RUNNING = 'RUNNING'
    SUCCESS = 'SUCCESS'
    RESTORED = 'RESTORED'
    FAILED = 'FAILED'
    FAILED_WAITING = 'FAILED_WAITING'
    CANCELED = 'CANCELED'
    SPECIAL = 'SPECIAL'

    _FAILED_STATUSES = {
        FAILED,
        CANCELED,
        FAILED_WAITING,
    }

    _SUCCEEDED_STATUSES = {
        STATIC,
        SUCCESS,
        RESTORED,
        SPECIAL,
    }

    _FINISHED_STATUSES = _FAILED_STATUSES | _SUCCEEDED_STATUSES

    @staticmethod
    def is_finished(node_running_status):
        """Check if the status is final"""
        return node_running_status in NodeRunningStatus._FINISHED_STATUSES

    @staticmethod
    def is_succeeded(node_running_status):
        """Check if the status is final and successful"""
        return node_running_status in NodeRunningStatus._SUCCEEDED_STATUSES

    @staticmethod
    def is_failed(node_running_status):
        """Check if the status is final and failed"""
        return node_running_status in NodeRunningStatus._FAILED_STATUSES


class NodeStatus:
    """Node permanent status"""
    CREATED = 'CREATED'
    READY = 'READY'
    DEPRECATED = 'DEPRECATED'
    MANDATORY_DEPRECATED = 'MANDATORY_DEPRECATED'


class NodePostAction:
    """HTTP post action"""
    SAVE = 'SAVE'
    APPROVE = 'APPROVE'
    CREATE_RUN = 'CREATE_RUN'
    CLONE = 'CLONE'
    VALIDATE = 'VALIDATE'
    DEPRECATE = 'DEPRECATE'
    MANDATORY_DEPRECATE = 'MANDATORY_DEPRECATE'
    PREVIEW_CMD = 'PREVIEW_CMD'
    REARRANGE_NODES = 'REARRANGE_NODES'
    UPGRADE_NODES = 'UPGRADE_NODES'
    CANCEL = 'CANCEL'
    GENERATE_CODE = 'GENERATE_CODE'


class NodePostStatus:
    """Standard HTTP response status"""
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    VALIDATION_FAILED = 'VALIDATION_FAILED'


class NodeClonePolicy:
    """Clone algorithm"""
    NODE_TO_NODE = 0
    NODE_TO_RUN = 1
    RUN_TO_NODE = 2


class NodeVirtualCollection:
    """Virtual collection"""
    OPERATIONS = 'operations'
    WORKFLOWS = 'workflows'


class SpecialNodeId:
    """Special Node IDs in the workflows"""
    INPUT = ObjectId('2419f9500000000000000000')
    OUTPUT = ObjectId('56274ccc0000000000000000')


class NodeOrigin:
    """Enum that indicates where the Node came from"""
    DB = "DB"
    BUILT_IN_HUBS = "BUILT_IN_HUBS"
