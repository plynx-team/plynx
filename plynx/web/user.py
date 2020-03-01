from flask import g
from plynx.db.demo_user_manager import DemoUserManager
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors
from plynx.utils.common import JSONEncoder
from plynx.constants import Collections


demo_user_manager = DemoUserManager()


@app.route('/plynx/api/v0/token', strict_slashes=False)
@requires_auth
@handle_errors
def get_auth_token():
    access_token = g.user.generate_access_token()
    refresh_token = g.user.generate_refresh_token()
    return JSONEncoder().encode({
        'access_token': access_token.decode('ascii'),
        'refresh_token': refresh_token.decode('ascii')
    })


@app.route('/plynx/api/v0/demo', methods=['POST'])
@handle_errors
def post_demo_user():
    user = demo_user_manager.create_demo_user()
    if not user:
        return make_fail_response('Failed to create a demo user')

    access_token = user.generate_access_token(expiration=1800)
    return JSONEncoder().encode({
        'access_token': access_token.decode('ascii'),
        'refresh_token': 'Not assigned',
        'username': user.username,
        'url': '/{}/{}'.format(Collections.TEMPLATES, DemoUserManager.demo_config.kind),
    })
