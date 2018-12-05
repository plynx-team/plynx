import copy
from past.builtins import basestring
from bson.objectid import ObjectId
from plynx.api import InvalidTypeArgumentError, MissingArgumentError, \
    Inputs, Outputs, Params, BaseNode

REQUIRED_ARGUMENTS = {
    'id'
}

ARGUMENT_TYPES = {
    'id': basestring,
    'title': basestring,
    'description': basestring,
    'inputs': list,
    'params': list,
    'outputs': list
}


def Node(**kwargs):
    class NodeClass(BaseNode):
        def __init__(self, **extra_args):
            super(NodeClass, self).__init__()
            args = copy.deepcopy(kwargs)
            args.update(extra_args)
            for key in REQUIRED_ARGUMENTS:
                if key not in args:
                    raise MissingArgumentError('`{}` is requered'.format(key))
            for arg_name, arg_type in ARGUMENT_TYPES.items():
                if arg_name in args and not isinstance(args[arg_name], arg_type):
                    raise InvalidTypeArgumentError('`{}` is expected to be an instance of {}'.format(key, arg_type))

            self._id = ObjectId()
            self.title = extra_args.get('title', kwargs.get('title', ''))
            self.description = extra_args.get('description', kwargs.get('description', ''))

            self.parent_node = args.get('id', '')
            if not self.parent_node:
                raise MissingArgumentError('`id` is requered')

            self.inputs = Inputs(args.get('inputs', []), **args)
            self.params = Params(args.get('params', []), **args)
            self.outputs = Outputs(self, args.get('outputs', []))

            # same values across all nodes
            self.base_node_name = ''
            self.node_running_status = ''

    return NodeClass


def File(**kwargs):
    return Node(outputs=['out'])(**kwargs)


Operation = Node
