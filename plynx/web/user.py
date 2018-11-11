#!/usr/bin/env python
from flask import request, abort, g
from plynx.db import DemoUserManager
from plynx.web import app, requires_auth, register_user
from plynx.utils.common import JSONEncoder


demo_user_manager = DemoUserManager()


@app.route('/plynx/api/v0/users', methods=['POST'])
def new_user():
    username = request.json.get('username')
    password = request.json.get('password')

    message = register_user(username, password)

    if message:
        abort(400, message)

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
