"""The serving logic of the worker"""
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
    data = json.loads(request.data)
    run_id = data["run_id"]

    response = post_request("get_run", data={"run_id": run_id})
    if response:
        node_dict = response["node"]
    else:
        return make_fail_response("Could not find the run"), 404

    node: Node = Node.from_dict(node_dict)

    executor = materialize_executor(node)
    db_executor = DBJobExecutor(executor)
    db_executor.run()

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
