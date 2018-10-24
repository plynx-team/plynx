class MissingArgumentError(ValueError):
    pass


class TooManyArgumentsError(ValueError):
    pass


class InvalidTypeArgumentError(TypeError):
    pass


class NodeAttributeError(AttributeError):
    pass


class ApiActionError(RuntimeError):
    pass


class InvalidUssageError(RuntimeError):
    pass


class GraphFailed(RuntimeError):
    pass
