import re
from plynx.db.user import User

def validate_user(email, username, password):
    """Validates users credentials

    Args:
        email          (str)   Email
        username       (str)   Username
        password       (str)   Password
        confpassword   (str)   Confirm Password

    Return:
        (bool)         True if credentials are valid else False

        (str)         Email error message

        (str)         Username error message

        (str)         Password error message
    """
    emailError = ''
    usernameError = ''
    passwordError = ''
    success = False

    user = User()

    if not re.match(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email):
        emailError = "Invalid email"
        success = False
    elif user.find_user_by_email(email):
        emailError = "Email is alredy in use"
        success = False

    if len(username) < 6:
        usernameError = "Username must be 6 charcters or more"
        success = False
    elif len(username) > 22:
        usernameError = "Username must be 22 charcters or less"
        success = False
    elif user.find_user_by_name(username):
        usernameError = "Username is alredy taken"
        success = False

    if not re.match(r"^(?=.*?[A-Z])(?=(.*[a-z]){1,})(?=(.*[\d]){1,})(?!.*\s).{8,}$", password):
        passwordError = 'Password must have at least 8 characters, including an uppercase letter and a number'
        success = False

    return success, emailError, usernameError, passwordError
