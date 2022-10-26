"""Templates for PLynx Resources and utils."""
from collections import namedtuple
from typing import Any, Dict, Optional

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
    DISPLAY_THUMBNAIL: bool = False

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
    def preprocess_input(value: Any) -> Any:
        """Resource preprocessor"""
        return value

    @staticmethod
    def postprocess_output(value: Any) -> Any:
        """Resource postprocessor"""
        return value

    @classmethod
    def preview(cls, preview_object: PreviewObject) -> str:
        """Preview Resource"""
        # TODO escape html code for security reasons
        data = _force_decode(preview_object.fp.read())
        return f"<pre>{data}</pre>"

    @classmethod
    def thumbnail(cls, output: Any) -> Optional[str]:   # pylint: disable=unused-argument
        """Thumbnail preview Resource"""
        return None
