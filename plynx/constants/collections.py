"""Standard PLynx collections in DB"""


class Collections:
    """All basic collections used in DB"""
    NODE_CACHE = 'node_cache'
    RUN_CANCELLATIONS = 'run_cancellations'
    RUNS = 'runs'
    TEMPLATES = 'templates'
    USERS = 'users'
    WORKER_STATE = 'worker_state'

    # virtual collections:
    HUB_NODE_REGISTRY = 'hub_node_registry'
