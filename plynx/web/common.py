import re
import logging
import traceback
from flask import Flask, request, g, Response
from flask_cors import CORS
from functools import wraps
from plynx.constants import ResponseStatus, RegisterUserExceptionCode
from plynx.db.user import User, UserCollectionManager
from plynx.utils.config import get_config
from plynx.utils.common import JSONEncoder
from plynx.utils.exceptions import RegisterUserException
from plynx.utils.db_connector import check_connection

app = Flask(__name__)

DEFAULT_EMAIL = ''
DEFAULT_USERNAME = 'default'
DEFAULT_PASSWORD = ''

_config = None


def verify_password(username_or_token, password):
    if _config and _config.auth.secret_key and username_or_token == DEFAULT_USERNAME:
        return False
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = UserCollectionManager.find_user_by_name(username_or_token)
        if not user or not user.verify_password(password):
            return False
    g.user = user
    return True


def authenticate():
    # 401 response
    return Response(
        'Could not verify your access level for that URL; You have to login with proper credentials',
        401,
        {'WWW-Authenticate': 'PlynxBasic realm="Login Required"'}
    )


def requires_auth(f):
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


def register_user(username, password, email):
    """Register a new user.

    Args:
        username    (str):  Username
        password    (str):  Pasword
        email       (str):  Email

    Return:
        (User):     New user DB Object
    """
    if not username:
        raise RegisterUserException(
            'Missing username',
            error_code=RegisterUserExceptionCode.EMPTY_USERNAME
        )
    if not password:
        raise RegisterUserException(
            'Missing password',
            error_code=RegisterUserExceptionCode.EMPTY_PASSWORD
        )
    if UserCollectionManager.find_user_by_name(username):
        raise RegisterUserException(
            'Username is taken',
            error_code=RegisterUserExceptionCode.USERNAME_ALREADY_EXISTS
        )
    if not re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email):
        raise RegisterUserException(
            'Invalid email: `{}`'.format(email),
            error_code=RegisterUserExceptionCode.INVALID_EMAIL
        )
    if UserCollectionManager.find_user_by_email(email):
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
    user.save()
    return user


def _init_default_user():

    if not UserCollectionManager.find_user_by_name(DEFAULT_USERNAME):
        message = register_user(DEFAULT_EMAIL, DEFAULT_USERNAME, DEFAULT_PASSWORD)
        if message:
            raise Exception(message)
        logging.info('Created default user `{}`'.format(DEFAULT_USERNAME))
    else:
        logging.info('Default user `{}` already exists'.format(DEFAULT_USERNAME))


def make_fail_response(message, **kwargs):
    return JSONEncoder().encode({
        'status': ResponseStatus.FAILED,
        'message': message,
        **kwargs
    })


def make_permission_denied(message='Permission denied'):
    return make_fail_response(message), 403


def make_success_response(extra_response=None):
    return JSONEncoder().encode(dict(
        {
            'status': ResponseStatus.SUCCESS,
            'message': 'Success',
            'settings': g.user.settings.to_dict(),
        }, **(extra_response or {})))


def handle_errors(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            app.logger.error(traceback.format_exc())
            return make_fail_response('Internal error: "{}"'.format(repr(e))), 500
    return decorated


def run_api():
    global _config
    _config = get_config()

    check_connection()

    # Create default user if in single user mode
    if not _config.auth.secret_key:
        logging.info('Single user mode')
        _init_default_user()
    else:
        logging.info('Multiple user mode')

    CORS(app, resources={r"/*": {"origins": "*"}})
    app.run(
        host=_config.web.host,
        port=_config.web.port,
        debug=_config.web.debug,
        use_reloader=False,
    )
