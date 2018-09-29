import datetime
from . import DBObject
from utils.db_connector import *
from utils.common import to_object_id, ObjectId


class Feedback(DBObject):
    """
    Basic Feedback class with db interface
    """

    def __init__(self, feedback_id=None):
        super(Feedback, self).__init__()
        self._id = None
        self.name = ''
        self.email = ''
        self.message = ''
        self.url = ''

        if feedback_id:
            self._id = to_object_id(feedback_id)
            self.load()

        if not self._id:
            self._id = ObjectId()

    def to_dict(self):
        return {
            "_id": self._id,
            "name": self.name,
            "email": self.email,
            "message": self.message,
            "url": self.url
        }

    def save(self, force=False):
        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        feedback_dict = self.to_dict()
        feedback_dict["update_date"] = now

        db.feedback.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": feedback_dict
            },
            upsert=True,
        )

        self._dirty = False
        return True

    def load(self):
        if self._id:
            feedback = db.feedback.find_one({'_id': self._id})
        if feedback is None:
            raise Exception("User not found")
        self.load_from_dict(feedback)

    def load_from_dict(self, feedback_dict):
        for key, value in feedback_dict.iteritems():
            setattr(self, key, value)
        self._id = to_object_id(self._id)
        self._dirty = False

    def __str__(self):
        return 'Feedback(_id="{}", user={})'.format(self._id, self.user)

    def __repr__(self):
        return 'User({})'.format(self.to_dict())

    def __getattr__(self, name):
        raise Exception("Can't get attribute '{}'".format(name))


if __name__ == "__main__":
    feedback = Feedback()
    feedback.user = 'test'
    feedback.message = 'hello'
    print(feedback.__repr__())
    feedback.save()
