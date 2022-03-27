"""Validation Error DB Object and utils"""
from dataclasses import dataclass, field
from typing import List

from dataclasses_json import dataclass_json

from plynx.db.db_object import DBObject


@dataclass_json
@dataclass
class ValidationError(DBObject):
    """Basic Validation Error class."""
    target: str
    object_id: str
    validation_code: str
    children: List["ValidationError"] = field(default_factory=list)
