import os
from plynx.api.exceptions import TooManyArgumentsError
from plynx.api.api import _get_access_token


class Client(object):
    def __init__(self, token=None, token_path=None, endpoint=None):
        self.endpoint = endpoint or \
            os.environ.get('PLYNX_ENDPOINT', '') or \
            'http://plynx.com/plynx/api/v0'

        if token and token_path:
            raise TooManyArgumentsError(
                "`token and token_path` cannot be set both in the same time"
            )
        if token:
            self._refresh_token = token
        else:
            token_path = token_path or \
                os.environ.get('PLYNX_TOKEN_PATH', '') or \
                os.path.join(os.path.expanduser("~"), '.plynx_token')

            if not os.path.exists(token_path):
                raise ValueError(
                    'You must specify `token` or `token_path`. Default file `{}` not found'.format(token_path)
                )
            with open(token_path) as f:
                self._refresh_token = f.readline().rstrip()

        self.access_token = None

    def update_token(self):
        self.access_token = _get_access_token(self._refresh_token, self)

    def get_token(self):
        if not self.access_token:
            self.update_token()
        return self.access_token
