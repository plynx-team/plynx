from . import Block, Input, Output, Parameter, ParameterWidget
from constants import FileTypes, ParameterTypes
import unittest

def get_test_block():
    block = Block()
    block.title = 'Command 1x1'
    block.description = 'Any command with 1 arg'
    block.base_block_name = "command"
    block.inputs = [
        Input(
            name='in',
            file_types=[FileTypes.FILE],
            values=[])
        ]
    block.outputs = [
        Output(
            name='out',
            file_type=FileTypes.FILE,
            resource_id=None
            )
        ]
    block.parameters = [
        Parameter(
            name='text',
            parameter_type=ParameterTypes.STR,
            value='test text',
            widget=ParameterWidget(
                alias = 'text'
                )
            ),
        Parameter(
            name='cmd',
            parameter_type=ParameterTypes.STR,
            value='cat ${input[in]} | grep ${param[text]} > ${output[out]}',
            widget=ParameterWidget(
                alias = 'Command line'
                )
            ),
        ]
    return block

def compare_dictionaries(dict1, dict2):
     if dict1 == None or dict2 == None:
         return True

     if not isinstance(dict1, dict) or not isinstance(dict2, dict):
         return False

     shared_keys = set(dict2.keys()) & set(dict2.keys())

     if not ( len(shared_keys) == len(dict1.keys()) and len(shared_keys) == len(dict2.keys())):
         return False

     dicts_are_equal = True
     for key in dict1.keys():
         if isinstance(dict1[key], dict):
             dicts_are_equal = dicts_are_equal and compare_dictionaries(dict1[key], dict2[key])
         else:
             dicts_are_equal = dicts_are_equal and (dict1[key] == dict2[key])

     return dicts_are_equal

class TestBlock(unittest.TestCase):
    
    def test_serialization(self):
        block1 = get_test_block()
        block1_dict = block1.to_dict()
        block2 = Block()
        block2.load_from_dict(block1_dict)
        block2_dict = block2.to_dict()

        self.assertTrue(compare_dictionaries(block1_dict, block2_dict), "Serialized blocks are not equal")

if __name__ == '__main__':
    unittest.main()