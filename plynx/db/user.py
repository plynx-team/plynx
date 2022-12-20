"""User DB Object and utils"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Union

import jwt
from dataclasses_json import dataclass_json
from passlib.apps import custom_app_context as pwd_context

from plynx.constants import Collections, TokenType
from plynx.db.db_object import DBObject
from plynx.utils.common import ObjectId
from plynx.utils.config import get_auth_config, get_iam_policies_config
from plynx.utils.db_connector import get_db_connector

DEFAULT_POLICIES = get_iam_policies_config().default_policies
JWT_ENCODE_ALGORITHM = "HS256"


@dataclass_json
@dataclass
class UserSettings(DBObject):
    """User Settings structure."""
    display_name: str = ""
    picture: str = ""


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
        self.password_hash = pwd_context.encrypt(password) if password else ""  # pylint: disable=attribute-defined-outside-init

    def verify_password(self, password: str) -> bool:
        """Verify password.

        Args:
            password    (str)   Real password string

        Return:
            (bool)    True if password matches else False
        """
        return pwd_context.verify(password, self.password_hash)

    def check_role(self, role: str) -> bool:
        """Check if the user has a given role"""
        return role in self.policies

    @staticmethod
    def find_users() -> List[Dict]:
        """Get all the users"""
        return getattr(get_db_connector(), User.DB_COLLECTION).find({})

    def generate_token(self, token_type: str, expiration: int = 600) -> str:
        """Generate a token.

        Args:
            token_type  (str)   Either TokenType.ACCESS_TOKEN, or TokenType.REFRESH_TOKEN
            expiration  (int)   Time to Live (TTL) in sec

        Return:
            (str)   Secured token
        """
        payload: Dict[str, Union[str, datetime]] = {
            "username": self.username,
            "type": token_type,
        }

        if token_type == TokenType.ACCESS_TOKEN:
            payload["exp"] = datetime.now(tz=timezone.utc) + timedelta(seconds=expiration)
        elif token_type == TokenType.REFRESH_TOKEN:
            payload["exp"] = datetime.now(tz=timezone.utc) + timedelta(hours=720)
        else:
            raise ValueError(f"`token_type` is unknown value `{token_type}`")

        token = jwt.encode(payload, get_auth_config().secret_key, algorithm=JWT_ENCODE_ALGORITHM)

        return token

    @staticmethod
    def verify_auth_token(token: str) -> Optional["User"]:
        """Verify token.

        Args:
            token   (str)   Token

        Return:
            (User)   User object or None
        """
        try:
            payload = jwt.decode(token, get_auth_config().secret_key, algorithms=[JWT_ENCODE_ALGORITHM])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
        except Exception as e:  # pylint: disable=broad-except
            print(f"Unexpected exception: {e}")
            return None

        user = UserCollectionManager.find_user_by_name(payload['username'])
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
