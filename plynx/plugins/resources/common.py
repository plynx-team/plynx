import os
import stat
import json
import zipfile
from plynx.constants import NodeResources
from plynx.base import resource
from plynx.utils.common import zipdir
from plynx.utils.config import get_web_config

WEB_CONFIG = get_web_config()


class Raw(resource.BaseResource):
    DISPLAY_RAW = True


class File(resource.BaseResource):
    pass


class PDF(resource.BaseResource):
    @classmethod
    def preview(cls, preview_object):
        return '<iframe src="{}" title="preview" type="application/pdf" width="100%"/>'.format(
            '{}/resource/{}'.format(
                WEB_CONFIG.endpoint,
                preview_object.resource_id),
        )


class Image(resource.BaseResource):
    @classmethod
    def preview(cls, preview_object):
        return '<img src="{}" width="100%" alt="preview" />'.format(
            '{}/resource/{}'.format(
                WEB_CONFIG.endpoint,
                preview_object.resource_id),
        )


class _BaseSeparated(resource.BaseResource):
    SEPARATOR = None
    _ROW_CLASSES = ['even', 'odd']
    _NUM_ROW_CLASSES = len(_ROW_CLASSES)

    @classmethod
    def preview(cls, preview_object):
        preview_object.fp.truncate(1024 ** 2)
        line_data = []
        for idx, line in enumerate(preview_object.fp.read().decode('utf-8').split('\n')):
            line_data.append(
                '<tr class="preview-table-row-{}">{}</tr>'.format(
                    cls._ROW_CLASSES[idx % cls._NUM_ROW_CLASSES],
                    ''.join(map(lambda s: '<td class="preview-table-col">{}</td>'.format(s), line.split(cls.SEPARATOR)))
                )
            )
        return '<table class="preview-table">{}</table>'.format('\n'.join(line_data))


class CSV(_BaseSeparated):
    SEPARATOR = ','


class TSV(_BaseSeparated):
    SEPARATOR = '\t'


class Json(resource.BaseResource):
    @classmethod
    def preview(cls, preview_object):
        if preview_object.fp.getbuffer().nbytes > 1024 ** 2:
            return super(Json, cls).preview(preview_object)
        try:
            return '<pre>{}</pre>'.format(
                json.dumps(json.loads(preview_object.fp.read().decode('utf-8')), indent=2)
            )
        except Exception as e:
            return 'Failed to parse json: {}'.format(e)


class Executable(resource.BaseResource):
    @staticmethod
    def prepare_input(filename, preview):
        # `chmod +x` to the executable file
        if preview:
            return {NodeResources.INPUT: filename}
        st = os.stat(filename)
        os.chmod(filename, st.st_mode | stat.S_IEXEC)
        return {NodeResources.INPUT: filename}


class Directory(resource.BaseResource):
    @staticmethod
    def prepare_input(filename, preview):
        # extract zip file
        if preview:
            return {NodeResources.INPUT: filename}
        zip_filename = '{}.zip'.format(filename)
        os.rename(filename, zip_filename)
        os.mkdir(filename)
        with zipfile.ZipFile(zip_filename) as zf:
            zf.extractall(filename)
        return {NodeResources.INPUT: filename}

    @staticmethod
    def prepare_output(filename, preview):
        if preview:
            return {NodeResources.OUTPUT: filename}
        os.mkdir(filename)
        return {NodeResources.OUTPUT: filename}

    @staticmethod
    def postprocess_output(filename):
        zip_filename = '{}.zip'.format(filename)
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
            zipdir(filename, zf)
        return zip_filename

    @classmethod
    def preview(cls, preview_object):
        with zipfile.ZipFile(preview_object.fp, 'r') as zf:
            content_stream = '\n'.join(zf.namelist())

        return '<pre>{}</pre>'.format(content_stream)


FILE_KIND = 'file'
