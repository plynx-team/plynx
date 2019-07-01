from plynx.db.node import Node
from plynx.db.input import Input
from plynx.db.parameter import Parameter, ParameterWidget
from plynx.db.output import Output
from plynx.constants import ParameterTypes
from plynx.plugins.resources import File as FileCls
import unittest


def get_test_node():
    node = Node()
    node.title = 'Command 1x1'
    node.description = 'Any command with 1 arg'
    node.base_node_name = "command"

    node.inputs = []
    node.inputs.append(Input())
    node.inputs[-1].name = 'in'
    node.inputs[-1].file_types = [FileCls.NAME]
    node.inputs[-1].values = []

    node.outputs = []
    node.outputs.append(Output())
    node.outputs[-1].name = 'out'
    node.outputs[-1].file_type = FileCls.NAME
    node.outputs[-1].resource_id = None

    node.parameters = []
    node.parameters.append(Parameter())
    node.parameters[-1].name = 'number'
    node.parameters[-1].parameter_type = ParameterTypes.INT
    node.parameters[-1].value = -1
    node.parameters[-1].widget = ParameterWidget.from_dict({'alias': 'Number'})

    node.parameters.append(Parameter())
    node.parameters[-1].name = 'cmd'
    node.parameters[-1].parameter_type = ParameterTypes.STR
    node.parameters[-1].value = 'cat ${input[in]} | grep ${param[text]} > ${output[out]}'
    node.parameters[-1].widget = ParameterWidget.from_dict({'alias': 'Command line'})

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


class TestNode(unittest.TestCase):

    def test_serialization(self):
        node1 = get_test_node()
        node1_dict = node1.to_dict()
        node2 = Node.from_dict(node1_dict)
        node2_dict = node2.to_dict()

        print(node1_dict)
        print("-")
        print(node2_dict)

        self.assertTrue(compare_dictionaries(node1_dict, node2_dict), "Serialized nodes are not equal")


if __name__ == '__main__':
    unittest.main()
