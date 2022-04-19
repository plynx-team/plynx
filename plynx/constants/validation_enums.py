"""Node validation enums"""


class ValidationTargetType:
    """Object Target"""
    BLOCK: str = 'BLOCK'
    GRAPH: str = 'GRAPH'
    INPUT: str = 'INPUT'
    NODE: str = 'NODE'
    PARAMETER: str = 'PARAMETER'
    PROPERTY: str = 'PROPERTY'


class ValidationCode:
    """Standard validation code"""
    IN_DEPENDENTS: str = 'IN_DEPENDENTS'
    MISSING_INPUT: str = 'MISSING_INPUT'
    MISSING_PARAMETER: str = 'MISSING_PARAMETER'
    INVALID_VALUE: str = 'INVALID_VALUE'
    DEPRECATED_NODE: str = 'DEPRECATED_NODE'
    EMPTY_GRAPH: str = 'EMPTY_GRAPH'
