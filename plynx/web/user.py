"""All of the endpoints related to Users"""

import json
import os

from flask import g, request
from google.auth.transport import requests as g_requests
from google.oauth2 import id_token

import plynx.db.node_collection_manager
from plynx.constants import Collections, IAMPolicies, TokenType, UserPostAction
from plynx.db.demo_user_manager import DemoUserManager
from plynx.db.user import User, UserCollectionManager
from plynx.utils.exceptions import RegisterUserException
from plynx.web.common import app, handle_errors, logger, make_fail_response, make_success_response, register_user, requires_auth

demo_user_manager = DemoUserManager()
template_collection_manager = plynx.db.node_collection_manager.NodeCollectionManager(collection=Collections.TEMPLATES)

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", None)


@app.route('/plynx/api/v0/token', strict_slashes=False)
@requires_auth
@handle_errors
def get_auth_token():
    """Generate access and refresh tokens"""
    access_token = g.user.generate_token(TokenType.ACCESS_TOKEN)
    refresh_token = g.user.generate_token(TokenType.REFRESH_TOKEN)

    user_obj = g.user.to_dict()
    user_obj['hash_password'] = ''
    return make_success_response({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user_obj,
    })


@app.route('/plynx/api/v0/users/<username>', methods=['GET'])
@handle_errors
@requires_auth
def get_user(username: str):
    """Get user info by username"""
    user = UserCollectionManager.find_user_by_name(username)
    if not user:
        return make_fail_response('User not found'), 404
    user_obj = user.to_dict()

    is_admin = IAMPolicies.IS_ADMIN in g.user.policies
    user_obj['_is_admin'] = is_admin
    user_obj['_readonly'] = user._id != g.user._id and not is_admin
    del user_obj['password_hash']

    return make_success_response({
        'user': user_obj,
        })


@app.route('/plynx/api/v0/users', methods=['POST'])
@handle_errors
@requires_auth
def post_user():
    """Update user info"""
    data = json.loads(request.data)
    logger.info(data)
    action = data.get('action', '')
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    if action == UserPostAction.MODIFY:
        posted_user = User.from_dict(data['user'])
        existing_user = UserCollectionManager.find_user_by_name(posted_user.username)
        if not existing_user:
            return make_fail_response('User not found'), 404
        if g.user.username != posted_user.username and IAMPolicies.IS_ADMIN not in g.user.policies:
            return make_fail_response('You don`t have permission to modify this user'), 401

        if set(posted_user.policies) != set(existing_user.policies):
            if IAMPolicies.IS_ADMIN not in g.user.policies:
                return make_fail_response('You don`t have permission to modify policies'), 401
            existing_user.policies = posted_user.policies

        if new_password:
            if not existing_user.verify_password(old_password):
                return make_fail_response('Incorrect password'), 401
            existing_user.hash_password(new_password)

        existing_user.settings = posted_user.settings

        existing_user.save()
        if g.user.username == posted_user.username:
            g.user = posted_user    # pylint: disable=assigning-non-slot

        is_admin = IAMPolicies.IS_ADMIN in g.user.policies
        user_obj = existing_user.to_dict()
        user_obj['_is_admin'] = is_admin
        user_obj['_readonly'] = existing_user._id != g.user._id and not is_admin
        del user_obj['password_hash']

        return make_success_response({
            'user': user_obj,
            })
    else:
        raise Exception(f"Unknown action: `{action}`")

    raise NotImplementedError("Nothing is to return")


@app.route('/plynx/api/v0/register', methods=['POST'])
@handle_errors
def post_register():
    """Register a new user"""
    query = json.loads(request.data)

    email = query['email'].lower()
    username = query['username']
    password = query['password']

    try:
        user = register_user(
            username=username,
            password=password,
            email=email,
        )
    except RegisterUserException as ex:
        return make_fail_response(
            ex.message,
            error_code=ex.error_code,
        ), 400

    g.user = user   # pylint: disable=assigning-non-slot
    access_token = user.generate_token(TokenType.ACCESS_TOKEN)
    refresh_token = user.generate_token(TokenType.REFRESH_TOKEN)

    user_obj = user.to_dict()
    user_obj['hash_password'] = ''
    return make_success_response({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user_obj,
    })


@app.route('/plynx/api/v0/register_with_oauth2', methods=['POST'])
@handle_errors
def post_register_with_oauth2():
    """Register a new user"""
    query = json.loads(request.data)
    token = query["token"]

    try:
        idinfo = id_token.verify_oauth2_token(token, g_requests.Request(), GOOGLE_CLIENT_ID)
    except ValueError:
        # Invalid token
        return make_fail_response("Invalid request"), 400

    if not idinfo["email_verified"]:
        return make_fail_response("Unable to verify the email"), 401

    username = idinfo['sub']
    user = UserCollectionManager.find_user_by_name(username)
    if not user:
        logger.info("The user does not exist. Creating a new one.")
        user = register_user(
            username=username,
            password="",
            email=idinfo["email"],
            picture=idinfo["picture"],
            is_oauth=True,
            display_name=idinfo["name"],
        )
        demo_user_manager.create_demo_templates(user)

    if user.settings.picture != idinfo["picture"]:
        user.settings.picture = idinfo["picture"]
        user.save()

    g.user = user   # pylint: disable=assigning-non-slot
    access_token = user.generate_token(TokenType.ACCESS_TOKEN)
    refresh_token = user.generate_token(TokenType.REFRESH_TOKEN)

    user_obj = user.to_dict()
    user_obj['hash_password'] = ''
    return make_success_response({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': user_obj,
    })
