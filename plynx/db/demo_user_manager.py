import string
import random
from plynx.db.user import User
from plynx.utils.config import get_demo_config


class DemoUserManager(object):
    """The class contains Demo user code."""
    demo_config = get_demo_config()

    @staticmethod
    def _id_generator(size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @staticmethod
    def create_demo_user():
        if not DemoUserManager.demo_config.enabled:
            return None

        user = User()
        user.username = 'demo-{}'.format(DemoUserManager._id_generator())
        user.hash_password(DemoUserManager._id_generator(size=8))
        user.save()
        return user
