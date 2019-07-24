from plynx.db.service_state import get_master_state
from plynx.utils.common import JSONEncoder
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors


@app.route('/plynx/api/v0/master_state', methods=['GET'])
@handle_errors
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
