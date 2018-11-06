#!/usr/bin/env python
import json
from plynx.db import Feedback
from flask import request
from plynx.web import app
from plynx.utils.common import JSONEncoder


@app.route('/plynx/api/v0/feedback', methods=['POST'])
def new_feedback():
    body = json.loads(request.data)['body']

    feedback = Feedback.from_dict(body)
    feedback.save(force=True)
    return JSONEncoder().encode({
        'status': 'success'
    })
