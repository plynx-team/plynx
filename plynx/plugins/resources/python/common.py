"""Commonly used Resource types and templates in python."""
import json
import os
import uuid
from typing import Any, Optional

import plynx.utils.file_handler
from plynx.base import resource


class Json(resource.BaseResource):
    """JSON file"""
    DISPLAY_THUMBNAIL: bool = True

    @staticmethod
    def preprocess_input(value: Any) -> Any:
        """Resource_id to an object"""

        with plynx.utils.file_handler.open(value, "r") as f:
            return json.load(f)

    @staticmethod
    def postprocess_output(value: Any) -> Any:
        """Object to resource id"""
        filename = str(uuid.uuid4())
        with plynx.utils.file_handler.open(filename, "w") as f:
            json.dump(value, f)
        return filename

    @classmethod
    def preview(cls, preview_object: resource.PreviewObject) -> str:
        """Generate preview html body"""
        res = json.load(preview_object.fp)
        return f"<pre>{json.dumps(res, indent=4)}</pre>"

    @classmethod
    def thumbnail(cls, output: Any) -> Optional[str]:
        if len(output.values) != 1:
            return None

        with plynx.utils.file_handler.open(output.values[0], "r") as f:
            res = json.load(f)
        formatted_text = json.dumps(res, indent=4)
        thumbnail_text = os.linesep.join(formatted_text.split(os.linesep)[:5])
        return f"<pre style='text-align:left; background:#222; margin:0; width:100%'>{thumbnail_text}...</pre>"
