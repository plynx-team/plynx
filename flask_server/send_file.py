#!/usr/bin/env python
from flask import send_file
from flask_server.pool import *
from os.path import join
from utils.config import getDataPath
from utils.file_handler import get_file_stream


@app.route("/get_image/<image_path>")
def get_image(image_path):
    root = 'image_tags/images/'
    image_file = get_file_stream(root + image_path)
    return send_file(image_file, attachment_filename=image_path, as_attachment=False)
