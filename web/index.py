#!/usr/bin/env python
from web.common import *
from web.graph import *
from web.resource import *

@app.route("/")
@app.route("/index")
def main():
    return render_template('index.html')


if __name__ == "__main__":
    urls_for()
    app.run()
