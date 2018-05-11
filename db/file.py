import copy
import datetime
from . import DBObject, Output, ValidationError
from utils.db_connector import *
from utils.common import to_object_id, ObjectId
from constants import BlockRunningStatus, FileStatus, FileTypes, ValidationTargetType, ValidationCode


class File(DBObject):
    """
    Basic file with db interface
    """

    PROPERTIES = {'outputs'}

    def __init__(self, file_id=None):
        super(File, self).__init__()

        self._id = None
        self._type = 'file'
        self.title = None
        self.description = None
        self.parent_file = None
        self.derived_from = None
        self.inputs = []
        self.outputs = []
        self.block_status = FileStatus.READY
        self.block_running_status = BlockRunningStatus.STATIC
        self.x = 0
        self.y = 0
        self.author = None
        self.public = False

        if file_id:
            self._id = to_object_id(file_id)
            self.load()
        else:
            self._id = ObjectId()

    def to_dict(self):
        return {
                "_id": self._id,
                "_type": self._type,
                "outputs": [output.to_dict() for output in self.outputs],
                "title": self.title,
                "description": self.description,
                "block_status": self.block_status,
                "derived_from": self.derived_from,
                "block_running_status": self.block_running_status,
                "x": self.x,
                "y": self.y,
                "author": self.author,
                "public": self.public
            }

    def load_from_dict(self, file_dict):
        for key, value in file_dict.iteritems():
            if key not in File.PROPERTIES:
                setattr(self, key, value)

        self._id = to_object_id(self._id)
        self.author = to_object_id(self.author)

        self.outputs = [Output.create_from_dict(output_dict) for output_dict in file_dict['outputs']]

    def copy(self):
        file = File()
        file.load_from_dict(self.to_dict())
        return file

    def save(self, force=False):
        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        file_dict = self.to_dict()
        file_dict["update_date"] = now

        db.files.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": file_dict
            },
            upsert=True,
            )

        self._dirty = False
        return True

    def load(self, file=None):
        if not file:
            file = db.files.find_one({'_id': self._id})
        if file:
            self.load_from_dict(file)
        self._dirty = False

    def copy(self):
        return copy.deepcopy(self)

    def get_validation_error(self):
        """Return validation error if found; else None"""
        violations = []
        if self.title == '':
            violations.append(
                ValidationError(
                    target=ValidationTargetType.PROPERTY,
                    object_id='title',
                    validation_code=ValidationCode.MISSING_PARAMETER
                ))

        if self.block_status != FileStatus.READY:
            violations.append(
                ValidationError(
                    target=ValidationTargetType.PROPERTY,
                    object_id='block_status',
                    validation_code=ValidationCode.INVALID_VALUE
                ))

        if self.block_running_status != BlockRunningStatus.STATIC:
            violations.append(
                ValidationError(
                    target=ValidationTargetType.PROPERTY,
                    object_id='block_running_status',
                    validation_code=ValidationCode.INVALID_VALUE
                ))

        if len(violations) == 0:
            return None

        return ValidationError(
                    target=ValidationTargetType.FILE,
                    object_id=str(self._id),
                    validation_code=ValidationCode.IN_DEPENDENTS,
                    children=violations
                    )

    def __str__(self):
        return 'File(_id="{}")'.format(self._id)

    def __repr__(self):
        return 'File({})'.format(str(self.to_dict()))

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            return super(File, self).__getattr__(name)
        raise Exception("Can't get attribute '{}'".format(name))

    def _get_custom_element(self, arr, name):
        for parameter in arr:
            if parameter.name == name:
                return parameter
        raise Exception('Parameter "{}" not found in {}'.format(name, self.title))

    def get_output_by_name(self, name):
        return self._get_custom_element(self.outputs, name)

    @staticmethod
    def get_default():
        file = File()
        file.title = 'File'
        file.description = 'Custom file'
        file.block_status = FileStatus.READY
        file.block_running_status = BlockRunningStatus.STATIC
        file.public = False

        return file



if __name__ == "__main__":
    from db import User
    user = User.find_user_by_name("khaxis")
    file = File()
    file.title = "File"
    file.description = "mnist.csv"
    file.block_status = FileStatus.READY
    file.author = user._id
    file.public = False
    file.outputs = [
        Output(
            name='out',
            file_type=FileTypes.CSV,
            resource_id="mnist.csv"
            )
        ]
    file.save()

    file = File()
    file.title = "File"
    file.description = "sample.py"
    file.block_status = FileStatus.READY
    file.author = user._id
    file.public = False
    file.outputs = [
        Output(
            name='out',
            file_type=FileTypes.EXECUTABLE,
            resource_id="sample.py"
            )
        ]
    file.save()

    file = File()
    file.title = "File"
    file.description = "train.py"
    file.block_status = FileStatus.READY
    file.author = user._id
    file.public = False
    file.outputs = [
        Output(
            name='out',
            file_type=FileTypes.EXECUTABLE,
            resource_id="train.py"
            )
        ]
    file.save()

    file = File()
    file.title = "File"
    file.description = "predict.py"
    file.block_status = FileStatus.READY
    file.author = user._id
    file.public = False
    file.outputs = [
        Output(
            name='out',
            file_type=FileTypes.EXECUTABLE,
            resource_id="predict.py"
            )
        ]
    file.save()

    file = File()
    file.title = "File"
    file.description = "build_plot.py"
    file.block_status = FileStatus.READY
    file.author = user._id
    file.public = False
    file.outputs = [
        Output(
            name='out',
            file_type=FileTypes.EXECUTABLE,
            resource_id='build_plot.py'
            )
        ]
    file.save()
