import os
import json
import re
from datetime import datetime
from bson import ObjectId
from collections import namedtuple

SearchParameter = namedtuple('SearchParameter', ['key', 'value'])

SEARCH_RGX = re.compile(r'[^-\s]+:[^-\s]+')


def to_object_id(_id):
    if type(_id) != ObjectId:
        _id = ObjectId(_id)
    return _id


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return str(o)
        return json.JSONEncoder.default(self, o)


def zipdir(path, zf):
    for root, dirs, files in os.walk(path):
        for file in files:
            arcname = os.path.relpath(os.path.join(root, file), os.path.join(path))
            zf.write(os.path.join(root, file), arcname)


def parse_search_string(search_string):
    found_matches = re.findall(SEARCH_RGX, search_string)
    search_parameters = dict([match.split(':') for match in found_matches])

    return search_parameters, ' '.join(re.sub(SEARCH_RGX, '', search_string).split())
