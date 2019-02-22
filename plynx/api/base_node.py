from plynx.api import InvalidTypeArgumentError, NodeAttributeError
import abc
import six


class NodeProps(object):
    def __init__(self, names):
        super(NodeProps, self).__init__()
        self._pyname_to_name = {
            name.replace('-', '_').replace('.', '_'): name for name in names
        }
        self._name_to_pyname = {v: k for k, v in self._pyname_to_name.items()}

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '{}({})'.format(
            self.__class__.__name__,
            ', '.join([
                '{}: {}'.format(
                    pyname,
                    getattr(self, pyname)
                ) for pyname in self._pyname_to_name.keys()
            ]
            )
        )

    def __setattr__(self, key, value):
        if '_initialized' in self.__dict__ and self._initialized and key not in self.__dict__:
            raise NodeAttributeError(
                '{} object has no attribute `{}`'
                .format(self.__class__.__name__, key)
            )
        self.__dict__[key] = value

    def __getitem__(self, name):
        return self.__getattribute__(self._name_to_pyname[name])

    def __setitem__(self, name, value):
        setattr(self, self._name_to_pyname[name], value)

    def __iter__(self):
        for name in self._name_to_pyname.keys():
            yield name

    def items(self):
        for name, pyname in self._name_to_pyname.items():
            yield name, self[name]


class Inputs(NodeProps):
    def __init__(self, names, **extra_args):
        super(Inputs, self).__init__(names)
        for pyname in self._pyname_to_name.keys():
            setattr(self, pyname, None)
        self._initialized = True
        for pyname, value in extra_args.items():
            if pyname in self._pyname_to_name:
                setattr(self, pyname, value)

    def __setattr__(self, key, value):
        if '_initialized' in self.__dict__ and self._initialized:
            if isinstance(value, list):
                for item in value:
                    if not isinstance(item, OutputItem):
                        raise InvalidTypeArgumentError(
                            'Expected type `{}`, got `{}`'.format(
                                OutputItem,
                                type(item)
                            )
                        )
            else:
                if value is not None and not isinstance(value, OutputItem):
                    raise InvalidTypeArgumentError(
                        'Expected type `{}`, got `{}`'.format(
                            OutputItem,
                            type(value)
                        )
                    )
                value = [value]
        super(Inputs, self).__setattr__(key, value)

    def _dictify(self):
        return [
            {
                'name': name,
                'values': [
                    output_item._dictify()
                    for output_item in getattr(self, pyname)
                ] if getattr(self, pyname) else []
            }
            for pyname, name in self._pyname_to_name.items()
        ]


class OutputItem(object):
    def __init__(self, node, output_name):
        self.node = node
        self.output_name = output_name

    def __repr__(self):
        return 'OutputItem({}: {})'.format(str(self.node), str(self.output_name))

    def _dictify(self):
        return {
            'output_id': self.output_name,
            'node_id': str(self.node._id),
            'resource_id': None
            }


class Outputs(NodeProps):
    def __init__(self, node, names):
        super(Outputs, self).__init__(names)
        for pyname, name in self._pyname_to_name.items():
            setattr(self, pyname, OutputItem(node, name))
        self._initialized = True

    def _dictify(self):
        return []


class Params(NodeProps):
    def __init__(self, names, **extra_args):
        super(Params, self).__init__(names)
        for pyname in self._pyname_to_name.keys():
            setattr(self, pyname, None)
        for pyname, value in extra_args.items():
            if pyname in self._pyname_to_name:
                setattr(self, pyname, value)
        self._initialized = True

    def _dictify(self):
        return [
            {'name': name, 'value': getattr(self, pyname)}
            for pyname, name in self._pyname_to_name.items()
        ]


@six.add_metaclass(abc.ABCMeta)
class BaseNode():
    def _dictify(self):
        node_dict = {
            'parent_node': self.parent_node,
            'description': self.description,
            'title': self.title,
            'node_running_status': self.node_running_status,
            'inputs': self.inputs._dictify(),
            'parameters': self.params._dictify(),
            'outputs': self.outputs._dictify(),
            'y': 0,
            'x': 0,
            '_id': str(self._id)

        }
        return node_dict
