"""Common utils of the web service."""

import logging
import re
import traceback
from functools import wraps
from typing import Any, Dict, Optional

from flask import Flask, Response, g, request
from flask.logging import create_logger
from flask_cors import CORS

from plynx.constants import RegisterUserExceptionCode, ResponseStatus
from plynx.db.user import User, UserCollectionManager
from plynx.utils.common import JSONEncoder
from plynx.utils.config import get_config
from plynx.utils.content import create_default_templates
from plynx.utils.db_connector import check_connection
from plynx.utils.exceptions import RegisterUserException

app = Flask(__name__)
logger = create_logger(app)

DEFAULT_EMAIL = ''
DEFAULT_USERNAME = 'default'
DEFAULT_PASSWORD = ''

_CONFIG = None


# pylint: disable=too-many-arguments
def register_user(username: str, password: str, email: str, picture: str = "", is_oauth: bool = False, display_name: Optional[str] = None) -> User:
    """
    Register a new user.
    """
    if not username:
        raise RegisterUserException(
            'Missing username',
            error_code=RegisterUserExceptionCode.EMPTY_USERNAME
        )
    if username != DEFAULT_USERNAME and not is_oauth and not password:
        raise RegisterUserException(
            'Missing password',
            error_code=RegisterUserExceptionCode.EMPTY_PASSWORD
        )
    if UserCollectionManager.find_user_by_name(username):
        raise RegisterUserException(
            'Username is taken',
            error_code=RegisterUserExceptionCode.USERNAME_ALREADY_EXISTS
        )
    if username != DEFAULT_USERNAME and not re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email):
        raise RegisterUserException(
            f"Invalid email: `{email}`",
            error_code=RegisterUserExceptionCode.INVALID_EMAIL
        )
    if username != DEFAULT_USERNAME and UserCollectionManager.find_user_by_email(email):
        raise RegisterUserException(
            'Email already exists',
            error_code=RegisterUserExceptionCode.EMAIL_ALREADY_EXISTS
        )
    if len(username) < 6 or len(username) > 22:
        raise RegisterUserException(
            'Lenght of the username must be between 6 and 22',
            error_code=RegisterUserExceptionCode.INVALID_LENGTH_OF_USERNAME
        )

    user = User()
    user.username = username
    user.email = email
    user.hash_password(password)
    user.settings.picture = picture
    user.settings.display_name = display_name or username
    user.save()
    return user


def _init_default_user():
    if UserCollectionManager.find_user_by_name(DEFAULT_USERNAME) is None:
        user = register_user(DEFAULT_USERNAME, DEFAULT_PASSWORD, DEFAULT_EMAIL)
        logging.info(f"Created default user `{DEFAULT_USERNAME}`")
        create_default_templates(user)
    else:
        logging.info(f"Default user `{DEFAULT_USERNAME}` already exists")


def verify_password(username_or_token: str, password: str):
    """Veryfy password based on user"""
    if _CONFIG and _CONFIG.auth.secret_key and username_or_token == DEFAULT_USERNAME:
        return False
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = UserCollectionManager.find_user_by_name(username_or_token)
        if not user or not user.verify_password(password):
            return False
    g.user = user   # pylint: disable=assigning-non-slot
    return True


def authenticate():
    """Return 401 message"""
    # 401 response
    return Response(
        'Could not verify your access level for that URL; You have to login with proper credentials',
        401,
        {'WWW-Authenticate': 'PlynxBasic realm="Login Required"'}
    )


def requires_auth(f):
    """Auth wrapper"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth:
            # if auth not provided, try default
            auth = {'username': DEFAULT_USERNAME, 'password': DEFAULT_PASSWORD}
        if not verify_password(auth['username'], auth['password']):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def make_fail_response(message, **kwargs):
    """Return basic fail response"""
    return JSONEncoder().encode({
        'status': ResponseStatus.FAILED,
        'message': message,
        **kwargs
    })


def make_permission_denied(message: str = 'Permission denied'):
    """Return permission error"""
    return make_fail_response(message), 403


def make_success_response(extra_response: Optional[Dict[str, Any]] = None):
    """Return successful response"""
    return JSONEncoder().encode(dict(
        {
            'status': ResponseStatus.SUCCESS,
            'message': 'Success',
            'settings': g.user.settings.to_dict() if hasattr(g, "user") else None,
        }, **(extra_response or {})))


def handle_errors(f):
    """Handle errors wrapper"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            logger.error(traceback.format_exc())
            return make_fail_response(f'Internal error: "{repr(e)}"'), 500
    return decorated


def run_api():
    """Run web service"""
    global _CONFIG  # pylint: disable=global-statement
    _CONFIG = get_config()

    check_connection()

    # Create default user if in single user mode
    if not _CONFIG.auth.secret_key:
        logging.info('Single user mode')
        _init_default_user()
    else:
        logging.info('Multiple user mode')

    CORS(app, resources={r"/*": {"origins": "*"}})
    app.run(
        host=_CONFIG.web.host,
        port=_CONFIG.web.port,
        debug=_CONFIG.web.debug,
        use_reloader=False,
        threaded=True,
    )
