#!/usr/bin/env python
from flask import Flask, request, send_file, abort, g, Response
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth
from functools import wraps
from plynx.db import User

app = Flask(__name__)
app.debug = True
CORS(app, resources={r"/*": {"origins": "*"}})


def verify_password(username_or_token, password):
    # TODO remove this one
    print(username_or_token, password)
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = User.find_user_by_name(username_or_token)
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
        if not auth or not verify_password(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
