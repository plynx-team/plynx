"""User Manager for demo"""
import random
import string
from typing import Optional

import plynx.db.node_collection_manager
from plynx.constants import Collections, NodeClonePolicy
from plynx.db.db_object import get_class
from plynx.db.node import Node
from plynx.db.user import User
from plynx.utils import node_utils
from plynx.utils.common import to_object_id
from plynx.utils.config import DemoConfig, get_demo_config

template_collection_manager = plynx.db.node_collection_manager.NodeCollectionManager(collection=Collections.TEMPLATES)


class DemoUserManager:
    """The class contains Demo user code."""
    demo_config: DemoConfig = get_demo_config()

    @staticmethod
    def _id_generator(size: int = 6, chars: str = string.ascii_uppercase + string.digits) -> str:
        return ''.join(random.choice(chars) for _ in range(size))

    @staticmethod
    def create_demo_user() -> Optional[User]:
        """Create a demo user"""
        if not DemoUserManager.demo_config.enabled:
            return None

        user = User()
        user.username = f"demo-{DemoUserManager._id_generator()}"
        user.hash_password(DemoUserManager._id_generator(size=8))
        user.save()
        return user

    @staticmethod
    def create_demo_templates(user):
        """
        Clone the default templates and assign them to the user.
        """
        if not DemoUserManager.demo_config.enabled:
            return

        # template_id = DemoUserManager.demo_config.kind
        for template_id in DemoUserManager.demo_config.template_ids:
            node_id = to_object_id(template_id)     # may raise bson.objectid.InvalidId
            node_dict = template_collection_manager.get_db_node(node_id, user._id)
            node: Node = get_class(node_dict['_type']).from_dict(node_dict).clone(NodeClonePolicy.NODE_TO_NODE)
            node.author = user._id
            node.latest_run_id = None
            node_utils.reset_nodes(node)
            node.save()
