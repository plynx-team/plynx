#!/usr/bin/env python
from flask import request, abort, g
from db import User, DemoUserManager
from web import app, requires_auth
from utils.common import JSONEncoder


demo_user_manager = DemoUserManager()


@app.route('/plynx/api/v0/users', methods=['POST'])
def new_user():
    username = request.json.get('username')
    password = request.json.get('password')

    if username is None or password is None:
        abort(400, 'Missing username')  # missing arguments

    if User.find_user_by_name(username):
        abort(400, 'User with name `{}` already exists'.format(username))

    user = User()
    user.username = username
    user.hash_password(password)
    user.save()
    return JSONEncoder().encode({
        'status': 'success'
    })


@app.route('/plynx/api/v0/token', strict_slashes=False)
@requires_auth
def get_auth_token():
    access_token = g.user.generate_access_token()
    refresh_token = g.user.generate_refresh_token()
    return JSONEncoder().encode({
        'access_token': access_token.decode('ascii'),
        'refresh_token': refresh_token.decode('ascii')
    })


@app.route('/plynx/api/v0/demo', methods=['POST'])
def post_demo_user():
    user = demo_user_manager.create_demo_user()
    demo_user_manager.create_demo_graphs(user)

    access_token = user.generate_access_token(expiration=1800)
    return JSONEncoder().encode({
        'access_token': access_token.decode('ascii'),
        'refresh_token': 'Not assigned',
        'username': user.username
    })
