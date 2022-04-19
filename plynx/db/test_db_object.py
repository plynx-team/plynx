"""Test DB object"""

from plynx.constants import ParameterTypes
from plynx.db.node import Input, Node, Output, Parameter


def get_test_node():
    """Create test node"""
    node = Node()
    node.title = 'Command 1x1'
    node.description = 'Any command with 1 arg'
    node.kind = "dummy"

    node.inputs = []
    node.inputs.append(
        Input(
            name="in",
            file_type="file",
            values=[],
        )
    )

    node.outputs = []
    node.outputs.append(
        Output(
            name="out",
            file_type="file",
        )
    )

    node.parameters = []
    node.parameters.append(
        Parameter(
            name="number",
            parameter_type=ParameterTypes.INT,
            value=-1,
            widget="Number",
        )
    )

    node.parameters.append(
        Parameter(
            name="cmd",
            parameter_type=ParameterTypes.STR,
            value="cat ${input[in]} | grep ${param[text]} > ${output[out]}",
            widget="Command line",
        )
    )

    return node


def compare_dictionaries(dict1, dict2):
    """Deep comparison of two dicts"""
    if dict1 is None or dict2 is None:
        return True

    if not isinstance(dict1, dict) or not isinstance(dict2, dict):
        return False

    shared_keys = set(dict2.keys()) & set(dict2.keys())

    if not (len(shared_keys) == len(dict1.keys()) and len(shared_keys) == len(dict2.keys())):
        return False

    dicts_are_equal = True
    for key in dict1.keys():
        if isinstance(dict1[key], dict):
            dicts_are_equal = dicts_are_equal and compare_dictionaries(dict1[key], dict2[key])
        else:
            dicts_are_equal = dicts_are_equal and (dict1[key] == dict2[key])

    return dicts_are_equal


def test_serialization():
    """Test serialization"""
    node1 = get_test_node()
    node1_dict = node1.to_dict()
    node2 = Node.from_dict(node1_dict)
    node2_dict = node2.to_dict()

    print(node1_dict)
    print("-")
    print(node2_dict)

    assert compare_dictionaries(node1_dict, node2_dict), "Serialized nodes are not equal"
