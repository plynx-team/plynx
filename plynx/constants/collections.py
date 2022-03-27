"""Standard PLynx collections in DB"""


class Collections:
    """All basic collections used in DB"""
    NODE_CACHE: str = 'node_cache'
    RUN_CANCELLATIONS: str = 'run_cancellations'
    RUNS: str = 'runs'
    TEMPLATES: str = 'templates'
    USERS: str = 'users'
    WORKER_STATE: str = 'worker_state'

    # virtual collections:
    HUB_NODE_REGISTRY: str = 'hub_node_registry'
