"""Standard PLynx types"""

ANY = "any"

STR_TO_CLASS = {
    "int": int,
    "str": str,
    "dict": dict,
    "float": float,
    "bool": bool,
    # Any other
    ANY: lambda x: x,
}

CLASS_TO_STR = {
    v: k for k, v in STR_TO_CLASS.items()
}


def type_to_str(type_cls):
    """Standard type to PLynx type"""
    return CLASS_TO_STR[type_cls]
