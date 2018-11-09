from collections import namedtuple


class WorkerMessageType:
    """Basic Massage type from Worker"""
    UNKNOWN = 0
    HEARTBEAT = 1
    GET_JOB = 2
    JOB_FINISHED_SUCCESS = 3
    JOB_FINISHED_FAILED = 4


class RunStatus:
    """Worker running status"""
    IDLE = 0
    RUNNING = 1
    SUCCESS = 2
    FAILED = 3


class MasterMessageType:
    """Basic Massage type from Master"""
    UNKNOWN = 0
    AKNOWLEDGE = 1
    SET_JOB = 2
    KILL = 3


WorkerMessage = namedtuple('WorkerMessage', ['worker_id', 'message_type', 'run_status', 'body', 'graph_id'])

MasterMessage = namedtuple('MasterMessage', ['worker_id', 'message_type', 'job', 'graph_id'])
