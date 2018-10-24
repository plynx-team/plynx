from . import Graph
from . import User
from plynx.utils.common import to_object_id, ObjectId
from plynx.utils.config import get_demo_config
from plynx.utils.db_connector import *
import string
import random


class DemoUserManager(object):
    """
    """
    demo_config = get_demo_config()

    @staticmethod
    def _id_generator(size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @staticmethod
    def create_demo_user():
        user = User()
        user.username = 'demo-{}'.format(DemoUserManager._id_generator())
        user.hash_password(DemoUserManager._id_generator(size=8))
        user.save()
        return user

    @staticmethod
    def create_demo_graphs(user):
        res = []
        for graph_id in DemoUserManager.demo_config.graph_ids:
            graph = Graph(graph_id)
            graph._id = ObjectId()
            graph.author = user._id
            graph.save()
            res.append(graph._id)
        return res
