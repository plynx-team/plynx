#!/usr/bin/env python
import json
from db import GraphCollectionManager
from db import User
from web.common import app, request, auth, abort, g
from utils.common import to_object_id, JSONEncoder


@app.route('/plynx/api/v0/users', methods = ['POST'])
def new_user():
    username = request.json.get('username')
    password = request.json.get('password')

    if username is None or password is None:
        abort(400, 'Missing username') # missing arguments

    if User.find_user_by_name(username):
        abort(400, 'User with name `{}` already exists'.format(username))

    user = User()
    user.username = username
    user.hash_password(password)
    user.save()
    return JSONEncoder().encode({
            'status':'success'
            })


@app.route('/plynx/api/v0/token')
@auth.login_required
def get_auth_token():
    access_token = g.user.generate_access_token()
    refresh_token = g.user.generate_refresh_token()
    return JSONEncoder().encode({
            'access_token': access_token.decode('ascii'),
            'refresh_token': refresh_token.decode('ascii')
            })


@auth.verify_password
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
