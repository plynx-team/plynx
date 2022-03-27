"""Main PLynx users service and utils"""
from typing import Optional

from plynx.db.user import User, UserCollectionManager

LIST_USERS = 'list_users'
CREATE_USER = 'create_user'
ACTIVATE_USER = 'activate_user'
DEACTIVATE_USER = 'deactivate_user'
MODES = [
    LIST_USERS,
    CREATE_USER,
    ACTIVATE_USER,
    DEACTIVATE_USER,
]


def run_list_users() -> None:
    """List all users"""
    for user_dict in User.find_users():
        user = User.from_dict(user_dict)
        print(','.join(map(str, [user._id, user.username])))


def run_create_user(email: Optional[str], username: Optional[str], password: Optional[str]) -> User:
    """Create a user"""
    if not username:
        raise ValueError('Username must be specified')
    password = password or ''
    user = User()
    user.username = username
    user.email = email
    user.hash_password(password)
    user.save()
    print(f"User `{username}` created")
    return user


def run_set_activation(username: Optional[str], value: bool) -> None:
    """Set user active status"""
    assert username, "Argument `username` is undifined"
    user = UserCollectionManager.find_user_by_name(username)

    if not user:
        raise ValueError(f"Username `{username}` not found")

    user.active = value
    user.save()
    print(f"User`s `{username}` active state changed to {value}")


def run_users(mode: str, email: Optional[str] = None, username: Optional[str] = None, password: Optional[str] = ''):
    """Users CLI entrypoint"""
    if mode not in MODES:
        raise ValueError(f"`mode` must be one of `{MODES}`. Value `{mode}` is given")
    if mode == LIST_USERS:
        run_list_users()
    elif mode == CREATE_USER:
        run_create_user(email, username, password)
    elif mode == ACTIVATE_USER:
        run_set_activation(username, True)
    elif mode == DEACTIVATE_USER:
        run_set_activation(username, False)
