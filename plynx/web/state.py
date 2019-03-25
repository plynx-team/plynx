#!/usr/bin/env python
from plynx.db import get_master_state
from plynx.utils.common import JSONEncoder
from plynx.web import app, requires_auth, make_fail_response


@app.route('/plynx/api/v0/master_state', methods=['GET'])
@requires_auth
def master_state():
    try:
        return JSONEncoder().encode({
            'status': 'success',
            'master_state': get_master_state()
        })
    except Exception as e:
        app.logger.error(e)
        return make_fail_response('Internal error: "{}"'.format(str(e)))
