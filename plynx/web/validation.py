import re
from plynx.db.user import User

def validate_user(**kwargs):
    " Validates users credentials, returns errors if any in dict. "
    dic = { 'success': True }

    user = User()

    if not re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", kwargs['email']):
        dic['email'] = "Invalid email"
        dic['success'] = False
    elif user.find_user_by_email(kwargs['email']):
        dic['email'] = "Email is alredy in use"
        dic['success'] = False
    else:
        dic['email'] = ''

    if len(kwargs['username']) < 6:
        dic['username'] = "Username must be 6 charcters or more"
        dic['success'] = False
    elif len(kwargs['username']) > 22:
        dic['username'] = "Username must be 22 charcters or less"
        dic['success'] = False
    elif user.find_user_by_name(kwargs['username']):
        dic['username'] = "Username is alredy taken"
        dic['success'] = False
    else:
        dic['username'] = ''

    if not re.match(r"^(?=.*?[A-Z])(?=(.*[a-z]){1,})(?=(.*[\d]){1,})(?!.*\s).{8,}$", kwargs['password']):
        dic['password'] = 'Password must have at least 8 characters, including an uppercase letter and a number'
        dic['success'] = False
    else:
        dic['password'] = ''

    if kwargs['password'] != kwargs['confpassword']:
        dic['confpassword'] = 'Password and confimation must match' 
        dic['success'] = False
    else:
        dic['confpassword'] = ''

    return dic