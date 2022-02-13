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


def type_to_str(tp):
    return CLASS_TO_STR[tp]
