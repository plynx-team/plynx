"""Standard PLynx types"""
from typing import Callable, Dict, Type, Union

ANY = "any"

STR_TO_CLASS: Dict[str, Union[Type, Callable]] = {
    "int": int,
    "str": str,
    "dict": dict,
    "float": float,
    "bool": bool,
    # Any other
    ANY: lambda x: x,
}

CLASS_TO_STR: Dict[Union[Type, Callable], str] = {
    v: k for k, v in STR_TO_CLASS.items()
}


def type_to_str(type_cls: Union[str, Type, Callable]) -> str:
    """Standard type to PLynx type"""
    if isinstance(type_cls, str):
        return type_cls
    return CLASS_TO_STR[type_cls]
