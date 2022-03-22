"""Node validation enums"""


class ValidationTargetType:
    """Object Target"""
    BLOCK = 'BLOCK'
    GRAPH = 'GRAPH'
    INPUT = 'INPUT'
    NODE = 'NODE'
    PARAMETER = 'PARAMETER'
    PROPERTY = 'PROPERTY'


class ValidationCode:
    """Standard validation code"""
    IN_DEPENDENTS = 'IN_DEPENDENTS'
    MISSING_INPUT = 'MISSING_INPUT'
    MISSING_PARAMETER = 'MISSING_PARAMETER'
    INVALID_VALUE = 'INVALID_VALUE'
    DEPRECATED_NODE = 'DEPRECATED_NODE'
    EMPTY_GRAPH = 'EMPTY_GRAPH'
