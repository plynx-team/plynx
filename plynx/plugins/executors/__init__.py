import os
import shutil
import pydoc
from abc import abstractmethod
import plynx.utils.exceptions
from plynx.db.node import Node


class BaseExecutor:
    ALIAS = None
    IS_GRAPH = False

    def __init__(self, node):
        self.node = node
        self.workdir = None

    @abstractmethod
    def run(self):
        pass

    @abstractmethod
    def status(self):
        pass

    @abstractmethod
    def kill(self):
        pass

    @staticmethod
    @abstractmethod
    def get_default_node(cls):
        pass

    def init_workdir(self):
        if not os.path.exists(self.workdir):
            os.makedirs(self.workdir)

    def clean_up(self):
        if os.path.exists(self.workdir):
            shutil.rmtree(self.workdir, ignore_errors=True)


def materialize_executor(node_dict):
    """
    Create a Node object from a dictionary

    Parameters:
    node_dict (dict): dictionary representation of a Node

    Returns:
    Node: Derived from plynx.nodes.base.Node class
    """
    kind = node_dict['kind']
    cls = pydoc.locate(kind)
    if not cls:
        raise plynx.utils.exceptions.NodeNotFound(
            'Node kind `{}` not found'.format(kind)
        )
    return cls(Node.from_dict(node_dict))
