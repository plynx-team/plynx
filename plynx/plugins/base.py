from plynx.constants import NodeResources

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
        pass

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
