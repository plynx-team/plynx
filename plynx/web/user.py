from flask import g, request, jsonify
from json import loads
import plynx.db.node_collection_manager
from plynx.db.db_object import get_class
from plynx.db.demo_user_manager import DemoUserManager
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors
from plynx.web.validation import validate_user
from plynx.utils.common import JSONEncoder, to_object_id
from plynx.constants import Collections, NodeClonePolicy
from plynx.utils.db_connector import get_db_connector
from plynx.utils.config import get_settings_config, get_auth_config
from plynx.service.users import run_create_user
from plynx.db.user import User
from itsdangerous import JSONWebSignatureSerializer as JSONserializer


demo_user_manager = DemoUserManager()
template_collection_manager = plynx.db.node_collection_manager.NodeCollectionManager(collection=Collections.TEMPLATES)

@app.route('/plynx/api/v0/token', strict_slashes=False)
@requires_auth
@handle_errors
def get_auth_token():
    access_token = g.user.generate_access_token()
    refresh_token = g.user.generate_refresh_token()
    return JSONEncoder().encode({
        'access_token': access_token.decode('ascii'),
        'refresh_token': refresh_token.decode('ascii'),
    })

@app.route('/plynx/api/v0/register', methods=['POST'])
@handle_errors
def post_register():
    email = request.headers.get('email').lower()
    username = request.headers.get('username').lower() 
    password = request.headers.get('password')

    dic = validate_user(
        email=email, 
        username=username, 
        password=password, 
        confpassword=request.headers.get('confpassword')
    )

    if dic['success']:
        user = run_create_user(email, username, password)
        access_token = user.generate_access_token()
        refresh_token = user.generate_refresh_token()
        dic['access_token'] = access_token.decode('ascii')
        dic['refresh_token'] = refresh_token.decode('ascii')
        return dic

    return dic

@app.route('/plynx/api/v0/demo', methods=['POST'])
@handle_errors
def post_demo_user():
    user = demo_user_manager.create_demo_user()
    if not user:
        return make_fail_response('Failed to create a demo user')

    template_id = DemoUserManager.demo_config.kind
    if DemoUserManager.demo_config.template_id:
        try:
            node_id = to_object_id(DemoUserManager.demo_config.template_id)
        except Exception as e:
            app.logger.error('node_id `{}` is invalid'.format(DemoUserManager.demo_config.template_id))
            app.logger.error(e)
            return make_fail_response('Failed to create a demo node')
        try:
            user_id = user._id
            node = template_collection_manager.get_db_node(node_id, user_id)
            node = get_class(node['_type'])(node).clone(NodeClonePolicy.NODE_TO_NODE)
            node.author = user_id
            node.save()
            template_id = node._id
        except Exception as e:
            app.logger.error('Failed to create a demo node')
            app.logger.error(e)
            return make_fail_response(str(e)), 500

    access_token = user.generate_access_token(expiration=1800)
    return JSONEncoder().encode({
        'access_token': access_token.decode('ascii'),
        'refresh_token': 'Not assigned',
        'username': user.username,
        'url': '/{}/{}'.format(Collections.TEMPLATES, template_id),
    })


@app.route('/plynx/api/v0/user_settings', methods=['POST'])
@handle_errors
def post_user_settings():
    data = loads(request.headers.get('values'))
    token = request.headers.get('token')

    userDOM = User()
    s = JSONserializer(get_auth_config().secret_key)
    username = s.loads(token)

    default_user = getattr(get_db_connector(), Collections.USERS).find_one({'username': username['username']})
    for i in default_user['settings']:
        if i[0] in data:
            i[1] = data[i[0]]
                
    getattr(get_db_connector(), Collections.USERS).save(default_user)
    return 'sucess'

@app.route('/plynx/api/v0/pull_settings', methods=['POST'])
@handle_errors
def post_pull_settings():
    token = request.headers.get('token')
    if token == 'undefined':
        return get_settings_config().settings
    
    userDOM = User()
    s = JSONserializer(get_auth_config().secret_key)
    username = s.loads(token)
    default_user = getattr(get_db_connector(), Collections.USERS).find_one({'username': username['username']})
    dic = get_settings_config().settings

    for i in default_user['settings']:
        dic[i[0]]['choice'] = i[1]
    
    return dic