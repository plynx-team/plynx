#!/usr/bin/env python
from gevent.wsgi import WSGIServer


if __name__ == "__main__":
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()
