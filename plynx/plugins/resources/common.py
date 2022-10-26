"""Commonly used Resource types."""

import json
import os
import stat
import zipfile
from typing import Any, Dict, List, Optional

from plynx.base import resource
from plynx.constants import NodeResources
from plynx.utils.common import zipdir
from plynx.utils.config import WebConfig, get_web_config

WEB_CONFIG: WebConfig = get_web_config()


class Raw(resource.BaseResource):
    """Raw Resource that will be stored in jsonable format in the Node."""
    DISPLAY_RAW: bool = True


class File(resource.BaseResource):
    """Raw Resource that will be stored in the file format in the Node."""


class PDF(resource.BaseResource):
    """PDF file"""
    @classmethod
    def preview(cls, preview_object: resource.PreviewObject) -> str:
        """Generate preview html body"""
        src_url = f"{WEB_CONFIG.endpoint}/resource/{preview_object.resource_id}"
        return f'<iframe src="{src_url}" title="preview" type="application/pdf" width="100%"/>'


class Image(resource.BaseResource):
    """Image file"""
    DISPLAY_THUMBNAIL: bool = True

    @classmethod
    def preview(cls, preview_object: resource.PreviewObject) -> str:
        """Generate preview html body"""
        src_url = f"{WEB_CONFIG.endpoint}/resource/{preview_object.resource_id}"
        return f'<img src="{src_url}" width="100%" alt="preview" />'

    @classmethod
    def thumbnail(cls, output: Any) -> Optional[str]:
        if len(output.values) != 1:
            return None
        src_url = f"{WEB_CONFIG.endpoint}/resource/{output.values[0]}"
        return f'<img src="{src_url}" width="100%" alt="preview" />'


class _BaseSeparated(resource.BaseResource):
    """Base Separated file, i.e. csv, tsv"""
    SEPARATOR: Optional[str] = None
    _ROW_CLASSES: List[str] = ['even', 'odd']
    _NUM_ROW_CLASSES: int = len(_ROW_CLASSES)

    @classmethod
    def preview(cls, preview_object: resource.PreviewObject) -> str:
        """Generate preview html body"""
        preview_object.fp.truncate(1024 ** 2)
        formated_lines = []
        for idx, line in enumerate(preview_object.fp.read().decode('utf-8').split('\n')):
            even_or_odd = cls._ROW_CLASSES[idx % cls._NUM_ROW_CLASSES]
            formated_cells = ''.join(map(lambda s: f'<td class="preview-table-col">{s}</td>', line.split(cls.SEPARATOR)))
            formated_line = f'<tr class="preview-table-row-{even_or_odd}">{formated_cells}</tr>'
            formated_lines.append(formated_line)
        all_lines = '\n'.join(formated_lines)
        return f'<table class="preview-table">{all_lines}</table>'


class CSV(_BaseSeparated):
    """CSV file"""
    SEPARATOR: str = ','


class TSV(_BaseSeparated):
    """TSV file"""
    SEPARATOR: str = '\t'


class Json(resource.BaseResource):
    """JSON file"""
    @classmethod
    def preview(cls, preview_object: resource.PreviewObject) -> str:
        """Generate preview html body"""
        if preview_object.fp.getbuffer().nbytes > 1024 ** 2:
            return super(Json, cls).preview(preview_object)
        try:
            readable_json = json.dumps(json.loads(preview_object.fp.read().decode('utf-8')), indent=2)
            return f"<pre>{readable_json}</pre>"
        except json.JSONDecodeError as e:
            return f"Failed to parse json: {e}"


class Executable(resource.BaseResource):
    """Executable file, i.e. bash or python"""
    @staticmethod
    def prepare_input(filename, preview: bool = False) -> Dict[str, str]:
        """Generate preview html body"""
        # `chmod +x` to the executable file
        if preview:
            return {NodeResources.INPUT: filename}
        file_status = os.stat(filename)
        os.chmod(filename, file_status.st_mode | stat.S_IEXEC)
        return {NodeResources.INPUT: filename}


class Directory(resource.BaseResource):
    """Directory file, i.e. zipfile"""
    @staticmethod
    def prepare_input(filename, preview: bool = False) -> Dict[str, str]:
        """Extract zip file"""
        if preview:
            return {NodeResources.INPUT: filename}
        zip_filename = f"{filename}.zip"
        os.rename(filename, zip_filename)
        os.mkdir(filename)
        with zipfile.ZipFile(zip_filename) as zf:
            zf.extractall(filename)
        return {NodeResources.INPUT: filename}

    @staticmethod
    def prepare_output(filename, preview: bool = False) -> Dict[str, str]:
        """Create output folder"""
        if preview:
            return {NodeResources.OUTPUT: filename}
        os.mkdir(filename)
        return {NodeResources.OUTPUT: filename}

    @staticmethod
    def postprocess_output(value: str) -> str:
        """Compress folder to a zip file"""
        zip_filename = f"{value}.zip"
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
            zipdir(value, zf)
        return zip_filename

    @classmethod
    def preview(cls, preview_object: resource.PreviewObject) -> str:
        """Generate preview html body"""
        with zipfile.ZipFile(preview_object.fp, 'r') as zf:
            content_stream = '\n'.join(zf.namelist())

        return f"<pre>{content_stream}</pre>"


FILE_KIND = 'file'
