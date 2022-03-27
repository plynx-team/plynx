"""Node Cache and utils"""

import hashlib
from builtins import str
from dataclasses import dataclass, field
from typing import List, Optional

from dataclasses_json import dataclass_json

from plynx.constants import Collections
from plynx.db.db_object import DBObject
from plynx.db.node import Output
from plynx.utils.common import ObjectId
from plynx.utils.config import get_demo_config

demo_config = get_demo_config()


@dataclass_json
@dataclass
class NodeCache(DBObject):
    """Basic Node Cache with db interface."""
    DB_COLLECTION = Collections.NODE_CACHE

    IGNORED_PARAMETERS = {'cmd', '_timeout'}

    _id: ObjectId = field(default_factory=ObjectId)
    key: str = ""
    node_id: Optional[ObjectId] = None
    run_id: Optional[ObjectId] = None
    outputs: List[Output] = field(default_factory=list)
    logs: List[Output] = field(default_factory=list)

    @staticmethod
    def instantiate(node, run_id):
        """Instantiate a Node Cache from Node.

        Args:
            node        (Node):             Node object
            run_id      (ObjectId, str):    Run ID

        Return:
            (NodeCache)
        """

        return NodeCache({
            'key': NodeCache.generate_key(node),
            'node_id': node._id,
            'run_id': run_id,
            'outputs': [output.to_dict() for output in node.outputs],
            'logs': [log.to_dict() for log in node.logs],
        })

    @staticmethod
    def generate_key(node):
        """Generate hash.

        Args:
            node        (Node):             Node object

        Return:
            (str)   Hash value
        """
        inputs = node.inputs
        parameters = node.parameters
        original_node_id = node.original_node_id

        sorted_inputs = sorted(inputs, key=lambda x: x.name)
        inputs_hash = ','.join([
            f"{input.name}:{','.join(sorted(input.values))}"
            for input in sorted_inputs
        ])

        sorted_parameters = sorted(parameters, key=lambda x: x.name)
        parameters_hash = ','.join([
            f"{parameter.name}:{parameter.value}"
            for parameter in sorted_parameters if parameter.name not in NodeCache.IGNORED_PARAMETERS
        ])

        return hashlib.sha256(
            ';'.join([
                    str(original_node_id),
                    inputs_hash,
                    parameters_hash,
                ]).encode('utf-8')
        ).hexdigest()
