"""User Manager for demo"""
import random
import string
from typing import Optional

from plynx.db.user import User
from plynx.utils.config import DemoConfig, get_demo_config


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
