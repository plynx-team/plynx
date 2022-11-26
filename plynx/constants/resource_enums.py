"""Resource enums"""


class NodeResources:
    """Internal node elements"""
    INPUT: str = 'inputs'
    OUTPUT: str = 'outputs'
    CLOUD_INPUT: str = 'cloud_inputs'
    CLOUD_OUTPUT: str = 'cloud_outputs'
    PARAM: str = 'params'
    LOG: str = 'logs'


class HubSearchParams:
    """Describing serach based on resource"""
    INPUT_FILE_TYPE: str = "input_file_type"
    OUTPUT_FILE_TYPE: str = "output_file_type"
