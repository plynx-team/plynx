"""Node constants"""
from typing import Set

from bson.objectid import ObjectId


class NodeRunningStatus:
    """Running status enum"""
    STATIC: str = 'STATIC'
    CREATED: str = 'CREATED'
    READY: str = 'READY'
    IN_QUEUE: str = 'IN_QUEUE'
    RUNNING: str = 'RUNNING'
    SUCCESS: str = 'SUCCESS'
    RESTORED: str = 'RESTORED'
    FAILED: str = 'FAILED'
    FAILED_WAITING: str = 'FAILED_WAITING'
    CANCELED: str = 'CANCELED'
    SPECIAL: str = 'SPECIAL'

    _FAILED_STATUSES: Set[str] = {
        FAILED,
        CANCELED,
        FAILED_WAITING,
    }

    _SUCCEEDED_STATUSES: Set[str] = {
        STATIC,
        SUCCESS,
        RESTORED,
        SPECIAL,
    }

    _AWAITING_STATUSES: Set[str] = {
        READY,
        IN_QUEUE,
        RUNNING,
    }

    _NON_CHANGEABLE_STATUSES: Set[str] = {
        STATIC,
        SPECIAL,
    }

    _FINISHED_STATUSES: Set[str] = _FAILED_STATUSES | _SUCCEEDED_STATUSES

    @staticmethod
    def is_finished(node_running_status: str) -> bool:
        """Check if the status is final"""
        return node_running_status in NodeRunningStatus._FINISHED_STATUSES

    @staticmethod
    def is_succeeded(node_running_status: str) -> bool:
        """Check if the status is final and successful"""
        return node_running_status in NodeRunningStatus._SUCCEEDED_STATUSES

    @staticmethod
    def is_failed(node_running_status: str) -> bool:
        """Check if the status is final and failed"""
        return node_running_status in NodeRunningStatus._FAILED_STATUSES

    @staticmethod
    def is_non_changeable(node_running_status: str) -> bool:
        """Check if the status is in static or special"""
        return node_running_status in NodeRunningStatus._NON_CHANGEABLE_STATUSES


class NodeStatus:
    """Node permanent status"""
    CREATED: str = 'CREATED'
    READY: str = 'READY'
    DEPRECATED: str = 'DEPRECATED'
    MANDATORY_DEPRECATED: str = 'MANDATORY_DEPRECATED'


class NodePostAction:
    """HTTP post action"""
    SAVE: str = 'SAVE'
    APPROVE: str = 'APPROVE'
    CREATE_RUN: str = 'CREATE_RUN'
    CREATE_RUN_FROM_SCRATCH: str = 'CREATE_RUN_FROM_SCRATCH'
    CLONE: str = 'CLONE'
    VALIDATE: str = 'VALIDATE'
    DEPRECATE: str = 'DEPRECATE'
    MANDATORY_DEPRECATE: str = 'MANDATORY_DEPRECATE'
    PREVIEW_CMD: str = 'PREVIEW_CMD'
    REARRANGE_NODES: str = 'REARRANGE_NODES'
    UPGRADE_NODES: str = 'UPGRADE_NODES'
    CANCEL: str = 'CANCEL'
    GENERATE_CODE: str = 'GENERATE_CODE'


class NodePostStatus:
    """Standard HTTP response status"""
    SUCCESS: str = 'SUCCESS'
    FAILED: str = 'FAILED'
    VALIDATION_FAILED: str = 'VALIDATION_FAILED'


class NodeClonePolicy:
    """Clone algorithm"""
    NODE_TO_NODE: int = 0
    NODE_TO_RUN: int = 1
    RUN_TO_NODE: int = 2


class NodeVirtualCollection:
    """Virtual collection"""
    OPERATIONS: str = 'operations'
    WORKFLOWS: str = 'workflows'


class SpecialNodeId:
    """Special Node IDs in the workflows"""
    INPUT: ObjectId = ObjectId('2419f9500000000000000000')
    OUTPUT: ObjectId = ObjectId('56274ccc0000000000000000')


class NodeOrigin:
    """Enum that indicates where the Node came from"""
    DB: str = "DB"
    BUILT_IN_HUBS: str = "BUILT_IN_HUBS"


IGNORED_CACHE_PARAMETERS = {'cmd', '_timeout'}
