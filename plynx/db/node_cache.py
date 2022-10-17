"""Node Cache and utils"""

import hashlib
from builtins import str
from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_json import dataclass_json

from plynx.constants import IGNORED_CACHE_PARAMETERS, Collections
from plynx.db.db_object import DBObject
from plynx.db.node import Node, Output
from plynx.utils.common import ObjectId
from plynx.utils.config import DemoConfig, get_demo_config

demo_config: DemoConfig = get_demo_config()


@dataclass_json
@dataclass
class NodeCache(DBObject):
    """Basic Node Cache with db interface."""
    # pylint: disable=too-many-instance-attributes
    DB_COLLECTION = Collections.NODE_CACHE

    _id: ObjectId = field(default_factory=ObjectId)
    key: str = ""
    node_id: Optional[ObjectId] = None
    run_id: Optional[ObjectId] = None
    outputs: List[Output] = field(default_factory=list)
    logs: List[Output] = field(default_factory=list)
    # TODO check if those are working
    removed: bool = False
    protected: bool = False

    @staticmethod
    def instantiate(node: Node, run_id: ObjectId) -> "NodeCache":
        """Instantiate a Node Cache from Node.

        Args:
            node    (Node):     Node object
            run_id  (ObjectId): Run ID

        Return:
            (NodeCache)
        """

        return NodeCache(
            key=NodeCache.generate_key(node),
            node_id=node._id,
            run_id=run_id,
            outputs=node.outputs,
            logs=node.logs,
        )

    @staticmethod
    def generate_key(node: Node) -> str:
        """Generate hash.

        Args:
            node    (Node): Node object

        Return:
            (str)   Hash value
        """
        inputs = node.inputs
        parameters = node.parameters
        original_node_id = node.original_node_id

        sorted_inputs = sorted(inputs, key=lambda x: x.name)
        inputs_hash = ','.join([
            f"{input.name}:{','.join(sorted(map(str, input.values)))}"
            for input in sorted_inputs
        ])

        sorted_parameters = sorted(parameters, key=lambda x: x.name)
        parameters_hash = ','.join([
            f"{parameter.name}:{parameter.value}"
            for parameter in sorted_parameters if parameter.name not in IGNORED_CACHE_PARAMETERS
        ])

        return hashlib.sha256(
            ';'.join([
                    str(original_node_id),
                    inputs_hash,
                    parameters_hash,
                ]).encode('utf-8')
        ).hexdigest()
