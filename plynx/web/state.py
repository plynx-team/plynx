from plynx.db.worker_state import get_worker_states
from plynx.utils.common import JSONEncoder
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors


@app.route('/plynx/api/v0/worker_states', methods=['GET', 'POST'])
@handle_errors
@requires_auth
def worker_states():
    try:
        return JSONEncoder().encode({
            'status': 'success',
            'items': get_worker_states()
        })
    except Exception as e:
        app.logger.error(e)
        return make_fail_response('Internal error: "{}"'.format(str(e)))
