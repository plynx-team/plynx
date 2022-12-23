"""
Service endpoints.
"""
# flake8: noqa
from gevent.pywsgi import WSGIServer

import plynx.web.health
import plynx.web.node
import plynx.web.resource
import plynx.web.run
import plynx.web.state
import plynx.web.user
from plynx.web.common import DEFAULT_EMAIL, DEFAULT_PASSWORD, DEFAULT_USERNAME, app, authenticate, make_fail_response, requires_auth, run_api, verify_password
