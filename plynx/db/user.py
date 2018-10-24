import datetime
from passlib.apps import custom_app_context as pwd_context
from . import DBObject
from plynx.utils.db_connector import *
from plynx.utils.common import to_object_id, ObjectId
from plynx.utils.config import get_auth_config
from itsdangerous import (SignatureExpired, BadSignature,
                          TimedJSONWebSignatureSerializer as TimedSerializer,
                          JSONWebSignatureSerializer as Serializer)


class User(DBObject):
    """
    Basic User class with db interface
    """

    AUTH_CONFIG = get_auth_config()

    def __init__(self, user_id=None):
        super(User, self).__init__()
        self._id = None
        self.username = None
        self.password_hash = None

        if user_id:
            self._id = to_object_id(user_id)
            self.load()
            assert username is None or self.username == username

        if not self._id:
            self._id = ObjectId()

    def to_dict(self):
        return {
            "_id": self._id,
            "username": self.username,
            "password_hash": self.password_hash
        }

    def save(self, force=False):
        assert isinstance(self._id, ObjectId)
        assert self.username
        assert self.password_hash

        if not self.is_dirty() and not force:
            return True

        now = datetime.datetime.utcnow()

        user_dict = self.to_dict()
        user_dict["update_date"] = now

        db.users.find_one_and_update(
            {'_id': self._id},
            {
                "$setOnInsert": {"insertion_date": now},
                "$set": user_dict
            },
            upsert=True,
        )

        self._dirty = False
        return True

    def load(self):
        if self._id:
            user = db.users.find_one({'_id': self._id})
        if user is None:
            raise Exception("User not found")
        self.load_from_dict(user)

    def load_from_dict(self, user):
        for key, value in user.iteritems():
            setattr(self, key, value)
        self._id = to_object_id(self._id)
        self._dirty = False

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)

    def generate_access_token(self, expiration=600):
        s = TimedSerializer(User.AUTH_CONFIG.secret_key, expires_in=expiration)
        return s.dumps({'username': self.username, 'type': 'access'})

    def generate_refresh_token(self):
        s = Serializer(User.AUTH_CONFIG.secret_key)
        return s.dumps({'username': self.username, 'type': 'refresh'})

    def __str__(self):
        return 'User(_id="{}", username={})'.format(self._id, self.username)

    def __repr__(self):
        return 'User({})'.format(self.to_dict())

    def __getattr__(self, name):
        raise Exception("Can't get attribute '{}'".format(name))

    @staticmethod
    def find_user_by_name(username):
        user_dict = db.users.find_one({'username': username})
        if not user_dict:
            return None

        user = User()
        user.load_from_dict(user_dict)
        return user

    @staticmethod
    def verify_auth_token(token):
        s = TimedSerializer(User.AUTH_CONFIG.secret_key)
        try:
            data = s.loads(token)
            if data['type'] != 'access':
                raise Exception('Not access token')
        except (BadSignature, SignatureExpired) as e:
            # access token is not valid or expired
            s = Serializer(User.AUTH_CONFIG.secret_key)
            try:
                data = s.loads(token)
                if data['type'] != 'refresh':
                    raise Exception('Not refresh token')
            except:
                return None
        except Exception as e:
            print("Unexpected exception: {}".format(e))
            return None
        user = User.find_user_by_name(data['username'])
        return user


if __name__ == "__main__":
    user = User()
    user.username = 'test'
    user.hash_password('test_pass')
    print(user.__repr__())
    user.save()
