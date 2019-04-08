import os
import stat
import zipfile
from plynx.constants import NodeResources
from plynx.plugins.base import BaseResource
from plynx.utils.common import zipdir


class File(BaseResource):
    NAME = 'file'
    ALIAS = 'File'
    ICON = 'feathericons.file'
    COLOR = '#fff'


class PDF(BaseResource):
    NAME = 'pdf'
    ALIAS = 'PDF file'
    ICON = 'plynx.pdf'
    COLOR = ''


class Image(BaseResource):
    NAME = 'image'
    ALIAS = 'Image'
    ICON = 'plynx.image'
    COLOR = ''


class CSV(BaseResource):
    NAME = 'csv'
    ALIAS = 'CSV file'
    ICON = 'plynx.csv'
    COLOR = ''


class TSV(BaseResource):
    NAME = 'tsv'
    ALIAS = 'TSV file'
    ICON = 'plynx.tsv'
    COLOR = ''


class Json(BaseResource):
    NAME = 'json'
    ALIAS = 'JSON file'
    ICON = 'plynx.json'
    COLOR = ''


class Executable(BaseResource):
    NAME = 'executable'
    ALIAS = 'Executable'
    ICON = 'feathericons.play'
    COLOR = '#fcff57'

    @staticmethod
    def prepare_input(filename, preview):
        # `chmod +x` to the executable file
        if preview:
            return {NodeResources.INPUT: filename}
        st = os.stat(filename)
        os.chmod(filename, st.st_mode | stat.S_IEXEC)
        return {NodeResources.INPUT: filename}


class Directory(BaseResource):
    NAME = 'directory'
    ALIAS = 'Directory'
    ICON = 'feathericons.folder'
    COLOR = '#f44'

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
