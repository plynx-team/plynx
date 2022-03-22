"""User DB Object and utils"""

# TODO: replace itsdangerous with more moder solution
from itsdangerous import BadSignature
from itsdangerous import JSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from itsdangerous import TimedJSONWebSignatureSerializer as TimedSerializer
from passlib.apps import custom_app_context as pwd_context

from plynx.constants import Collections, OperationViewSetting
from plynx.db.db_object import DBObject, DBObjectField
from plynx.utils.common import ObjectId
from plynx.utils.config import get_auth_config, get_iam_policies_config
from plynx.utils.db_connector import get_db_connector

DEFAULT_POLICIES = get_iam_policies_config().default_policies


class UserSettings(DBObject):
    """User Settings structure."""

    display_name: str

    FIELDS = {
        # settings
        'node_view_mode': DBObjectField(
            type=str,
            default=OperationViewSetting.KIND_AND_TITLE,
            is_list=False,
            ),
        'display_name': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
    }

    def __str__(self):
        return f'UserSettings(name="{self.display_name}")'

    def __repr__(self):
        return f'UserSettings({str(self.to_dict())})'


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
        'email': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'password_hash': DBObjectField(
            type=str,
            default='',
            is_list=False,
            ),
        'active': DBObjectField(
            type=bool,
            default=True,
            is_list=False,
            ),
        'policies': DBObjectField(
            type=str,
            default=DEFAULT_POLICIES,
            is_list=True,
            ),

        'settings': DBObjectField(
            type=UserSettings,
            default=UserSettings,
            is_list=False,
            ),
    }

    DB_COLLECTION = Collections.USERS

    def hash_password(self, password):
        """Change password.

        Args:
            password    (str)   Real password string
        """
        self.password_hash = pwd_context.encrypt(password)  # pylint: disable=attribute-defined-outside-init

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
        token = TimedSerializer(get_auth_config().secret_key, expires_in=expiration)
        return token.dumps({'username': self.username, 'type': 'access'})

    def generate_refresh_token(self):
        """Generate refresh token.

        Return:
            (str)   Secured token
        """
        token = Serializer(get_auth_config().secret_key)
        return token.dumps({'username': self.username, 'type': 'refresh'})

    def check_role(self, role):
        """Check if the user has a given role"""
        return role in self.policies

    def __str__(self):
        return f'User(_id="{self._id}", username={self.username})'

    def __repr__(self):
        return f'User({self.to_dict()})'

    def __getattr__(self, name):
        raise Exception(f"Can't get attribute '{name}'")

    @staticmethod
    def find_users():
        """Get all the users"""
        return getattr(get_db_connector(), User.DB_COLLECTION).find({})

    @staticmethod
    def verify_auth_token(token):
        """Verify token.

        Args:
            token   (str)   Token

        Return:
            (User)   User object or None
        """
        serializer = TimedSerializer(get_auth_config().secret_key)
        try:
            data = serializer.loads(token)
            if data['type'] != 'access':
                raise Exception('Not access token')
        except (BadSignature, SignatureExpired):
            # access token is not valid or expired
            serializer = Serializer(get_auth_config().secret_key)
            try:
                data = serializer.loads(token)
                if data['type'] != 'refresh':
                    raise Exception('No refresh token')     # pylint: disable=raise-missing-from
            except Exception:   # pylint: disable=broad-except
                return None
        except Exception as e:  # pylint: disable=broad-except
            print(f"Unexpected exception: {e}")
            return None
        user = UserCollectionManager.find_user_by_name(data['username'])
        if not user.active:
            return None
        return user


class UserCollectionManager:
    """User Manger"""
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
    def find_user_by_email(email):
        """Find User.

        Args:
            email    (str)   Email

        Return:
            (User)   User object or None
        """
        user_dict = getattr(get_db_connector(), User.DB_COLLECTION).find_one({'email': email})
        if not user_dict:
            return None

        return User(user_dict)

    @staticmethod
    def get_users(
            search='',
            per_page=20,
            offset=0,
            ):
        """Get a list of users"""
        raise NotImplementedError()
