"""Templates for PLynx Resources and utils."""
from collections import namedtuple
from typing import Dict

from plynx.constants import NodeResources

PreviewObject = namedtuple('PreviewObject', ['fp', 'resource_id'])


def _force_decode(byte_array):
    try:
        return byte_array.decode("utf-8")
    except UnicodeDecodeError:
        return f"# not a UTF-8 sequence:\n{byte_array}"
    return "Failed to decode the sequence"


class BaseResource:
    """Base Resource class"""
    DISPLAY_RAW: bool = False

    def __init__(self):
        pass

    @staticmethod
    def prepare_input(filename: str, preview: bool = False) -> Dict[str, str]:     # pylint: disable=unused-argument
        """Resource preprocessor"""
        return {NodeResources.INPUT: filename}

    @staticmethod
    def prepare_output(filename: str, preview: bool = False) -> Dict[str, str]:
        """Prepare output"""
        if not preview:
            # Create file
            with open(filename, 'a'):
                pass
        return {NodeResources.OUTPUT: filename}

    @staticmethod
    def postprocess_output(filename: str) -> str:
        """Resource postprocessor"""
        return filename

    @classmethod
    def preview(cls, preview_object: PreviewObject) -> str:
        """Preview Resource"""
        # TODO escape html code for security reasons
        data = _force_decode(preview_object.fp.read())
        return f"<pre>{data}</pre>"
