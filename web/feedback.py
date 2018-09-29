#!/usr/bin/env python
import json
from db import Feedback
from flask import request
from web import app
from utils.common import JSONEncoder


@app.route('/plynx/api/v0/feedback', methods=['POST'])
def new_feedback():
    body = json.loads(request.data)['body']

    feedback = Feedback()
    feedback.load_from_dict(body)
    feedback.save(force=True)
    return JSONEncoder().encode({
        'status': 'success'
    })
