from plynx.db import User


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


def run_list_users():
    for user_dict in User.find_users():
        user = User.from_dict(user_dict)
        print(','.join(map(str, [user._id, user.username])))


def run_create_user(username, password):
    if not username:
        raise ValueError('Usernmane must be specified')
    password = password or ''
    user = User()
    user.username = username
    user.hash_password(password)
    user.save()
    print('User `{}` created'.format(username))


def run_set_activation(username, value):
    user = User.find_user_by_name(username)

    if not user:
        raise ValueError("Username `{}` not found".format(username))

    user.active = value
    user.save()
    print('User`s `{}` active state changed to {}'.format(username, value))


def run_users(mode, username=None, password=''):
    if mode not in MODES:
        raise ValueError('`mode` must be one of `{values}`. Value `{mode}` is given'.format(
            values=MODES,
            mode=mode,
        ))
    if mode == LIST_USERS:
        run_list_users()
    elif mode == CREATE_USER:
        run_create_user(username, password)
    elif mode == ACTIVATE_USER:
        run_set_activation(username, True)
    elif mode == DEACTIVATE_USER:
        run_set_activation(username, False)
