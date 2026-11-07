"""
The class defines `DBObject`. This is an abstraction of all of the objects in database.
"""
import dataclasses
import datetime
import inspect
import types
from typing import Any, Dict, Optional, Type, TypeVar, Union, get_args, get_origin, no_type_check

from plynx.utils.common import ObjectId
from plynx.utils.db_connector import get_db_connector

DBObjectType = TypeVar("DBObjectType", bound="_DBObject")   # pylint: disable=invalid-name

_registry: Dict[str, Type[Any]] = {}


def register_class(target_class):
    """Register inherited from DB Object class"""
    _registry[target_class.__name__] = target_class


@no_type_check
def get_class(name: str) -> DBObjectType:
    """Get DB Object inherited class object by its name from the registry"""
    return _registry[name]


class DBObjectNotFound(Exception):
    """Internal Exception."""


class ClassNotSavable(Exception):
    """Internal Exception."""


class _DBObject:
    """DB Object.
    Abstraction of an object in the DB.
    """

    # Name of the collection in the database
    DB_COLLECTION = ""

    @classmethod
    def load(cls: Type[DBObjectType], _id: ObjectId, collection: Optional[str] = None) -> DBObjectType:
        """Load object from db.

        Args:
            _id     (ObjectId):    ID of the object in DB
        """
        collection = collection or cls.DB_COLLECTION
        obj_dict = getattr(get_db_connector(), collection).find_one({"_id": _id})
        if not obj_dict:
            raise DBObjectNotFound(f"Object `{_id}` not found in `{collection}` collection")
        return cls.from_dict(obj_dict)

    # TODO remove `force` argument or use it
    def save(self, force: bool = False, collection: Optional[str] = None):   # pylint: disable=unused-argument
        """Save Object in the database"""
        collection = collection or self.__class__.DB_COLLECTION
        if not collection:
            raise ClassNotSavable(
                f"Class `{self.__class__.__name__}` is not savable."
            )

        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)

        obj_dict = self.to_dict()
        obj_dict["update_date"] = now

        getattr(get_db_connector(), collection).find_one_and_update(
            {"_id": obj_dict["_id"]},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": obj_dict
            },
            upsert=True,
        )

        return True

    def copy(self: DBObjectType) -> DBObjectType:
        """Make a copy

        Return:
            A copy of the Object
        """
        return self.__class__.from_dict(self.to_dict())

    @classmethod
    def from_dict(cls: Type[DBObjectType], dict_obj: Dict[str, Any]) -> DBObjectType:   # type: ignore
        """Create a class based on dict_obj"""

    def to_dict(self: DBObjectType) -> Dict[str, Any]:
        """Create serialized object"""
        return {}

    def __str__(self) -> str:
        id_val = self.__dict__.get("_id", str(self.to_dict()))
        return f"{self.__class__.__name__}({id_val})"

    def __repr__(self) -> str:
        value = str(self.to_dict())
        return f"{self.__class__.__name__}({value})"


class Meta(type):
    """Class Registry handle"""
    def __new__(meta, name, bases, class_dict):     # pylint: disable=bad-mcs-classmethod-argument
        cls = type.__new__(meta, name, bases, class_dict)
        register_class(cls)
        return cls


class DBObject(_DBObject, metaclass=Meta):
    """
    DB Object.
    Abstraction of an object in the DB.

    Args:
        obj_dict    (dict, None):   Representation of the object. If None, an object with default fields will be created.
    """

    def __post_init__(self):
        if not dataclasses.is_dataclass(self):
            return
        for dc_field in dataclasses.fields(self):
            name = dc_field.name
            field_type = dc_field.type
            value = getattr(self, name)
            origin = get_origin(field_type)
            if origin in (Union, types.UnionType) and value is not None:
                non_none_types = [arg for arg in get_args(field_type) if arg is not types.NoneType]
                if len(non_none_types) == 1 and inspect.isclass(non_none_types[0]):
                    type_cls = non_none_types[0]
                    if not isinstance(value, type_cls):
                        converted = type_cls.from_dict(value) if issubclass(type_cls, _DBObject) and isinstance(value, dict) else type_cls(value)
                        setattr(self, name, converted)
            elif inspect.isclass(field_type) and value is not None and not isinstance(value, (field_type, _DBObject)):
                # Process external type, such as ObjectId
                setattr(self, name, field_type(value))
