#!/usr/bin/env python
from plynx.web.node import *
from plynx.web.common import *
from plynx.web.graph import *
from plynx.web.resource import *
from plynx.web.user import *
from plynx.web.feedback import *
from gevent.wsgi import WSGIServer


if __name__ == "__main__":
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()
