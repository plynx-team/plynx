"""Health check"""

from plynx.web.common import app, handle_errors


@app.route('/health', methods=['GET'])
@handle_errors
def get_health():
    """Health check"""
    return 'OK'
