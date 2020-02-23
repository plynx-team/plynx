from plynx.db.node import Node, Input, Parameter, Output
from plynx.constants import ParameterTypes


def get_test_node():
    node = Node()
    node.title = 'Command 1x1'
    node.description = 'Any command with 1 arg'
    node.kind = "dummy"

    node.inputs = []
    node.inputs.append(Input())
    node.inputs[-1].name = 'in'
    node.inputs[-1].file_type = 'file'
    node.inputs[-1].values = []

    node.outputs = []
    node.outputs.append(Output())
    node.outputs[-1].name = 'out'
    node.outputs[-1].file_type = 'file'

    node.parameters = []
    node.parameters.append(Parameter())
    node.parameters[-1].name = 'number'
    node.parameters[-1].parameter_type = ParameterTypes.INT
    node.parameters[-1].value = -1
    node.parameters[-1].widget = 'Number'

    node.parameters.append(Parameter())
    node.parameters[-1].name = 'cmd'
    node.parameters[-1].parameter_type = ParameterTypes.STR
    node.parameters[-1].value = 'cat ${input[in]} | grep ${param[text]} > ${output[out]}'
    node.parameters[-1].widget = 'Command line'

    return node


def compare_dictionaries(dict1, dict2):
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
    node1 = get_test_node()
    node1_dict = node1.to_dict()
    node2 = Node.from_dict(node1_dict)
    node2_dict = node2.to_dict()

    print(node1_dict)
    print("-")
    print(node2_dict)

    assert compare_dictionaries(node1_dict, node2_dict), "Serialized nodes are not equal"
