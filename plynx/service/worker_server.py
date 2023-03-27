"""The serving logic of the worker"""
import base64
import json
import logging

from flask import Flask, request
from flask.logging import create_logger
from flask_cors import CORS

from plynx.db.node import Node
from plynx.utils.executor import DBJobExecutor, materialize_executor, post_request
from plynx.utils.logs import set_logging_level
from plynx.web.common import make_fail_response, make_success_response

app = Flask(__name__)
logger = create_logger(app)


@app.route("/", methods=["POST"])
def execute_run():
    """Execute a run with a given id"""

    app.logger.warning("Endpoint / called")  # pylint: disable=no-member

    if False:   # pylint: disable=using-constant-test
        data = json.loads(request.data)
    else:
        envelope = request.get_json()
        if not envelope:
            msg = "no Pub/Sub message received"
            return make_fail_response(f"Bad Request: {msg}"), 400

        if not isinstance(envelope, dict) or "message" not in envelope:
            msg = "invalid Pub/Sub message format"
            app.logger.error(f"error: {msg}")   # pylint: disable=no-member
            return make_fail_response(f"Bad Request: {msg}"), 400

        pubsub_message = envelope["message"]

        if isinstance(pubsub_message, dict) and "data" in pubsub_message:
            message_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
            data = json.loads(message_str)
        else:
            return make_fail_response(f"Bad Request: {msg}"), 400

    run_id = data["run_id"]

    response = post_request("get_run", data={"run_id": run_id})
    if response:
        node_dict = response["node"]
    else:
        return make_fail_response("Could not find the run"), 404

    node: Node = Node.from_dict(node_dict)

    executor = materialize_executor(node)
    db_executor = DBJobExecutor(executor)
    app.logger.warning("Start running")  # pylint: disable=no-member
    db_executor.run()
    app.logger.warning("End running")   # pylint: disable=no-member

    return make_success_response({"node_running_status": node.node_running_status})


def run_worker_server(verbose, endpoint_port: int):
    """Run worker service"""

    # set up logger level
    set_logging_level(verbose, logger=logger)
    set_logging_level(verbose, logger=logging.getLogger('werkzeug'))

    CORS(app, resources={r"/*": {"origins": "*"}})
    app.run(
        host="0.0.0.0",
        port=endpoint_port,
        debug=True,
        use_reloader=False,
        threaded=True,
    )
