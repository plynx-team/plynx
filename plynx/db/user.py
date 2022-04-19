"""User DB Object and utils"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dataclasses_json import dataclass_json
# TODO: replace itsdangerous with more moder solution
from itsdangerous import BadSignature
from itsdangerous import JSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from itsdangerous import TimedJSONWebSignatureSerializer as TimedSerializer
from passlib.apps import custom_app_context as pwd_context

from plynx.constants import Collections, OperationViewSetting
from plynx.db.db_object import DBObject
from plynx.utils.common import ObjectId
from plynx.utils.config import get_auth_config, get_iam_policies_config
from plynx.utils.db_connector import get_db_connector

DEFAULT_POLICIES = get_iam_policies_config().default_policies


@dataclass_json
@dataclass
class UserSettings(DBObject):
    """User Settings structure."""
    node_view_mode: str = OperationViewSetting.KIND_AND_TITLE
    display_name: str = ""


@dataclass_json
@dataclass
class User(DBObject):
    """Basic User class with db interface."""
    DB_COLLECTION = Collections.USERS

    _id: ObjectId = field(default_factory=ObjectId)
    username: str = ""
    email: Optional[str] = ""
    password_hash: str = ""
    active: bool = True
    policies: List[str] = field(default_factory=lambda: list(DEFAULT_POLICIES))
    settings: UserSettings = field(default_factory=UserSettings)

    def hash_password(self, password: str):
        """Change password.

        Args:
            password    (str)   Real password string
        """
        self.password_hash = pwd_context.encrypt(password)  # pylint: disable=attribute-defined-outside-init

    def verify_password(self, password: str) -> bool:
        """Verify password.

        Args:
            password    (str)   Real password string

        Return:
            (bool)    True if password matches else False
        """
        return pwd_context.verify(password, self.password_hash)

    def generate_access_token(self, expiration: int = 600) -> str:
        """Generate access token.

        Args:
            expiration  (int)   Time to Live (TTL) in sec

        Return:
            (str)   Secured token
        """
        token = TimedSerializer(get_auth_config().secret_key, expires_in=expiration)
        return token.dumps({'username': self.username, 'type': 'access'})

    def generate_refresh_token(self) -> str:
        """Generate refresh token.

        Return:
            (str)   Secured token
        """
        token = Serializer(get_auth_config().secret_key)
        return token.dumps({'username': self.username, 'type': 'refresh'})

    def check_role(self, role: str) -> bool:
        """Check if the user has a given role"""
        return role in self.policies

    @staticmethod
    def find_users() -> List[Dict]:
        """Get all the users"""
        return getattr(get_db_connector(), User.DB_COLLECTION).find({})

    @staticmethod
    def verify_auth_token(token: str) -> Optional["User"]:
        """Verify token.

        Args:
            token   (str)   Token

        Return:
            (User)   User object or None
        """
        timed_serializer = TimedSerializer(get_auth_config().secret_key)
        try:
            data = timed_serializer.loads(token)
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
        if not user or not user.active:
            return None
        return user


class UserCollectionManager:
    """User Manger"""
    @staticmethod
    def find_user_by_name(username: str) -> Optional[User]:
        """Find User.

        Args:
            username    (str)   Username

        Return:
            (User)   User object or None
        """
        user_dict = getattr(get_db_connector(), User.DB_COLLECTION).find_one({'username': username})
        if not user_dict:
            return None

        return User.from_dict(user_dict)

    @staticmethod
    def find_user_by_email(email: str) -> Optional[User]:
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
            search: str = "",
            per_page: int = 20,
            offset: int = 0,
            ):
        """Get a list of users"""
        raise NotImplementedError()
