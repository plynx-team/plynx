import os
import sys
import json
import re
import collections
from datetime import datetime
from bson import ObjectId

SearchParameter = collections.namedtuple('SearchParameter', ['key', 'value'])

SEARCH_RGX = re.compile(r'[^\s]+:[^\s]+')

ObjectId = ObjectId


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


def query_yes_no(question, default='yes'):
    """Ask a yes/no question via input() and return their answer.

    Args:
        question    (str):  String that is presented to the user.
        default     (str):  'yes' or 'no' default value

    The 'answer' return value is True for 'yes' or False for 'no'.
    """
    valid = {'yes': True, 'y': True, 'ye': True,
             'no': False, 'n': False}
    if default is None:
        prompt = ' [y/n] '
    elif default == 'yes':
        prompt = ' [Y/n] '
    elif default == 'no':
        prompt = ' [y/N] '
    else:
        raise ValueError('invalid default answer: `%s`' % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")


def update_dict_recursively(dest, u):
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            dest[k] = update_dict_recursively(dest.get(k, {}), v)
        else:
            dest[k] = v
    return dest
