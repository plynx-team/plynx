#!/usr/bin/env python
from flask import Flask, render_template, request, send_file, url_for, abort, g
from flask_cors import CORS
from flask_httpauth import HTTPBasicAuth

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

auth = HTTPBasicAuth()

def urls_for():
    pass
    url_for('static', filename='style.css')
    url_for('static', filename='favicon.png')
