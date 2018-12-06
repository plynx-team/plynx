import logging
from plynx.api.exceptions import MissingArgumentError, InvalidTypeArgumentError, \
    NodeAttributeError, ApiActionError, InvalidUssageError, GraphFailed, \
    TooManyArgumentsError
from plynx.api.constants import _NodeRunningStatus, _GraphRunningStatus, \
    _GraphPostAction, _GraphPostStatus, _ValidationCode
from plynx.api.api import _get_obj, _save_graph, _get_access_token
from plynx.api.base_node import NodeProps, Inputs, OutputItem, Outputs, Params, BaseNode
from plynx.api.node import Node, Operation, File
from plynx.api.client import Client
from plynx.api.graph import Graph


def set_logging_level(verbose):
    LOG_LEVELS = {
        0: logging.CRITICAL,
        1: logging.ERROR,
        2: logging.WARNING,
        3: logging.INFO,
        4: logging.DEBUG
    }
    logging.basicConfig(level=LOG_LEVELS.get(verbose, 4))


set_logging_level(3)

__all__ = [
    ApiActionError,
    BaseNode,
    Node,
    Client,
    File,
    Graph,
    GraphFailed,
    Inputs,
    InvalidTypeArgumentError,
    InvalidUssageError,
    MissingArgumentError,
    NodeAttributeError,
    NodeProps,
    Operation,
    OutputItem,
    Outputs,
    Params,
    TooManyArgumentsError,
    _NodeRunningStatus,
    _GraphPostAction,
    _GraphPostStatus,
    _GraphRunningStatus,
    _ValidationCode,
    _get_access_token,
    _get_obj,
    _save_graph,
    set_logging_level,
]
