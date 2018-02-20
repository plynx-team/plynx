#!/usr/bin/env python
from web.block import *
from web.common import *
from web.graph import *
from web.resource import *
from web.user import *
from gevent.wsgi import WSGIServer

@app.route("/")
@app.route("/index")
def main():
    return render_template('index.html')


if __name__ == "__main__":
    urls_for()
    http_server = WSGIServer(('', 5000), app)
    http_server.serve_forever()
