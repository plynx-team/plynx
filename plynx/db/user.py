from passlib.apps import custom_app_context as pwd_context
from plynx.constants import Collections
from plynx.db import DBObjectField, DBObject
from plynx.utils.db_connector import get_db_connector
from plynx.utils.common import ObjectId
from plynx.utils.config import get_auth_config
from itsdangerous import (SignatureExpired, BadSignature,
                          TimedJSONWebSignatureSerializer as TimedSerializer,
                          JSONWebSignatureSerializer as Serializer)


class User(DBObject):
    """Basic User class with db interface."""

    FIELDS = {
        '_id': DBObjectField(
            type=ObjectId,
            default=ObjectId,
            is_list=False,
            ),
        'username': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'password_hash': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
    }

    DB_COLLECTION = Collections.USERS

    def hash_password(self, password):
        """Change password.

        Args:
            password    (str)   Real password string
        """
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        """Verify password.

        Args:
            password    (str)   Real password string

        Return:
            (bool)    True if password matches else False
        """
        return pwd_context.verify(password, self.password_hash)

    def generate_access_token(self, expiration=600):
        """Generate access token.

        Args:
            expiration  (int)   Time to Live (TTL) in sec

        Return:
            (str)   Secured token
        """
        s = TimedSerializer(get_auth_config().secret_key, expires_in=expiration)
        return s.dumps({'username': self.username, 'type': 'access'})

    def generate_refresh_token(self):
        """Generate refresh token.

        Return:
            (str)   Secured token
        """
        s = Serializer(get_auth_config().secret_key)
        return s.dumps({'username': self.username, 'type': 'refresh'})

    def __str__(self):
        return 'User(_id="{}", username={})'.format(self._id, self.username)

    def __repr__(self):
        return 'User({})'.format(self.to_dict())

    def __getattr__(self, name):
        raise Exception("Can't get attribute '{}'".format(name))

    @staticmethod
    def find_user_by_name(username):
        """Find User.

        Args:
            username    (str)   Username

        Return:
            (User)   User object or None
        """
        user_dict = getattr(get_db_connector(), User.DB_COLLECTION).find_one({'username': username})
        if not user_dict:
            return None

        return User(user_dict)

    @staticmethod
    def verify_auth_token(token):
        """Verify token.

        Args:
            token   (str)   Token

        Return:
            (User)   User object or None
        """
        s = TimedSerializer(get_auth_config().secret_key)
        try:
            data = s.loads(token)
            if data['type'] != 'access':
                raise Exception('Not access token')
        except (BadSignature, SignatureExpired) as e:
            # access token is not valid or expired
            s = Serializer(get_auth_config().secret_key)
            try:
                data = s.loads(token)
                if data['type'] != 'refresh':
                    raise Exception('Not refresh token')
            except Exception:
                return None
        except Exception as e:
            print("Unexpected exception: {}".format(e))
            return None
        user = User.find_user_by_name(data['username'])
        return user
