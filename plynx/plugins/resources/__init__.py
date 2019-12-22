from collections import namedtuple
from plynx.constants import NodeResources

PreviewObject = namedtuple('PreviewObject', ['fp', 'resource_id'])


def _force_decode(byte_array):
    try:
        return byte_array.decode('utf-8')
    except UnicodeDecodeError:
        return '# not a UTF-8 sequence:\n{}'.format(byte_array)
    return 'Failed to decode the sequence'


class BaseResource(object):
    NAME = None
    ALIAS = None
    ICON = None
    COLOR = None

    def __init__(self):
        assert type(self).NAME, 'NAME must be specified'
        assert type(self).ALIAS, 'ALIAS must be specified'
        assert type(self).ICON, 'ICON must be specified'
        assert type(self).COLOR is not None, 'COLOR must be specified'

    @classmethod
    def to_dict(cls):
        return {
            'name': cls.NAME,
            'alias': cls.ALIAS,
            'icon': cls.ICON,
            'color': cls.COLOR,
        }

    @staticmethod
    def prepare_input(filename, preview=False):
        return {NodeResources.INPUT: filename}

    @staticmethod
    def prepare_output(filename, preview=False):
        if not preview:
            with open(filename, 'a'):
                pass
        return {NodeResources.OUTPUT: filename}

    @staticmethod
    def postprocess_output(filename):
        return filename

    @classmethod
    def preview(cls, preview_object):
        preview_object.fp.truncate(1024 ** 2)  # 1 MB
        # TODO escape html code for security reasons
        return '<pre>{}</pre>'.format(_force_decode(preview_object.fp.read()))
