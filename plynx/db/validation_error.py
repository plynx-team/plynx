from past.builtins import basestring


# TODO use DBObject. The problem is that it will depend on itself recursively
class ValidationError(object):
    """Basic Validation Error class."""

    def __init__(self, target, object_id, validation_code, children=None):
        children = children or []
        assert isinstance(target, basestring), "validation value error"
        assert isinstance(object_id, basestring), "validation value error"
        assert isinstance(validation_code, basestring), "validation value error"
        assert isinstance(children, list), "validation value error"
        self.target = target
        self.object_id = object_id
        self.validation_code = validation_code
        self.children = children

    def to_dict(self):
        return {
            'target': self.target,
            'object_id': self.object_id,
            'validation_code': self.validation_code,
            'children': [child.to_dict() for child in self.children]
        }

    def __str__(self):
        return 'ValidationError({}, {}, {}, {})'.format(
            self.target,
            self.object_id,
            self.validation_code,
            self.children
        )

    def __repr__(self):
        return 'ValidationError({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(ValidationError, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))
