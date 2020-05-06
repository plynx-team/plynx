from collections import namedtuple
from abc import abstractmethod

_QUERY_FIELDS = (
    ('status', ''),
    ('search', ''),
    ('per_page', 30),
    ('offset', 0),
    ('user_id', None),
)

Query = namedtuple(
    'Query',
    field_names=[field[0] for field in _QUERY_FIELDS],
    defaults=[field[1] for field in _QUERY_FIELDS],
    )


class BaseHub(object):
    def __init__(self):
        pass

    @abstractmethod
    def search(self, query):
        pass
