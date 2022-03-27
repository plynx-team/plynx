"""Endpoints responsible for the dashboard"""
import plynx.utils.plugin_manager
from plynx.db.worker_state import get_worker_states
from plynx.web.common import app, handle_errors, logger, make_fail_response, make_success_response, requires_auth

PLUGINS_DICT = plynx.utils.plugin_manager.get_plugins_dict()


@app.route('/plynx/api/v0/worker_states', methods=['GET', 'POST'])
@handle_errors
@requires_auth
def worker_states():
    """Get worker's states"""
    try:
        return make_success_response({
            'items': list(map(lambda worker_state: worker_state.to_dict(), get_worker_states())),
            'plugins_dict': PLUGINS_DICT,
        })
    except Exception as e:  # pylint: disable=broad-except
        logger.error(e)
        return make_fail_response(f'Internal error: "{e}"')
