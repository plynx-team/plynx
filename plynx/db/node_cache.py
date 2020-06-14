import hashlib
from builtins import str
from plynx.constants import Collections
from plynx.db.db_object import DBObject, DBObjectField
from plynx.db.node import Output
from plynx.utils.common import ObjectId
from plynx.utils.config import get_demo_config

demo_config = get_demo_config()


class NodeCache(DBObject):
    """Basic Node Cache with db interface."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        'key': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'run_id': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'node_id': DBObjectField(
            type=ObjectId,
            default=None,
            is_list=False,
            ),
        'outputs': DBObjectField(
            type=Output,
            default=list,
            is_list=True,
            ),
        'logs': DBObjectField(
            type=Output,
            default=list,
            is_list=True,
            ),
    }

    DB_COLLECTION = Collections.NODE_CACHE

    IGNORED_PARAMETERS = {'cmd', '_timeout'}

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
            '{}:{}'.format(
                input.name,
                ','.join(sorted(input.values))
            )
            for input in sorted_inputs
        ])

        sorted_parameters = sorted(parameters, key=lambda x: x.name)
        parameters_hash = ','.join([
            '{}:{}'.format(
                parameter.name,
                parameter.value
            )
            for parameter in sorted_parameters if parameter.name not in NodeCache.IGNORED_PARAMETERS
        ])

        return hashlib.sha256(
            ';'.join([
                    str(original_node_id),
                    inputs_hash,
                    parameters_hash,
                ]).encode('utf-8')
        ).hexdigest()

    def __str__(self):
        return 'NodeCache(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'NodeCache({})'.format(str(self.to_dict()))
