"""Common utils"""
import collections
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from typing import Any, Dict, Tuple, Union

from bson import ObjectId

SearchParameter = collections.namedtuple('SearchParameter', ['key', 'value'])

SEARCH_RGX = re.compile(r'[^\s]+:[^\s]+')


def to_object_id(_id: Union[ObjectId, str, None]) -> ObjectId:
    """Create ObjectId based on str, or return original value."""
    if not isinstance(_id, ObjectId):
        assert isinstance(_id, str)
        _id = ObjectId(_id)
    return _id


class JSONEncoder(json.JSONEncoder):
    """Handles some of the built in types"""
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return str(o)
        return json.JSONEncoder.default(self, o)


def zipdir(path: str, zf: zipfile.ZipFile):
    """Walk in zip file"""
    for root, _, files in os.walk(path):
        for file in files:
            arcname = os.path.relpath(os.path.join(root, file), os.path.join(path))
            zf.write(os.path.join(root, file), arcname)


def parse_search_string(search_string: str) -> Tuple[Dict, str]:
    """Separate keywords fro mserach string"""
    found_matches = re.findall(SEARCH_RGX, search_string)
    search_parameters = dict([match.split(':') for match in found_matches])

    return search_parameters, ' '.join(re.sub(SEARCH_RGX, '', search_string).split())


def query_yes_no(question: str, default: str = 'yes') -> bool:
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
        raise ValueError(f"Invalid default answer: `{default}`")

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


def update_dict_recursively(dest: Dict[Any, Any], donor: Dict[Any, Any]) -> Dict[Any, Any]:
    """Update dictionary in place"""
    for k, v in donor.items():
        if isinstance(v, collections.Mapping):
            dest[k] = update_dict_recursively(dest.get(k, {}), v)   # type: ignore
        else:
            dest[k] = v
    return dest
