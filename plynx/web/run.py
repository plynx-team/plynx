"""All of the endpoints related to the the runs"""
import json

from flask import request

import plynx.db.node_collection_manager
import plynx.db.run_cancellation_manager
from plynx.constants import Collections
from plynx.db.node import Node
from plynx.utils.common import ObjectId
from plynx.web.common import app, handle_errors, make_fail_response, make_success_response

node_collection_manager = plynx.db.node_collection_manager.NodeCollectionManager(collection=Collections.RUNS)
run_cancellation_manager = plynx.db.run_cancellation_manager.RunCancellationManager()


@app.route('/plynx/api/v0/get_run', methods=['POST'])
@handle_errors
def get_a_run():
    """Find a certain run and return it"""
    data = json.loads(request.data)
    run_id = ObjectId(data["run_id"])

    node_dict = node_collection_manager.get_db_node(run_id)

    if node_dict is None:
        return make_fail_response(f"The run with id `{run_id}` is not found"), 404

    return make_success_response({"node": node_dict})


@app.route('/plynx/api/v0/pick_run', methods=['POST'])
@handle_errors
def pick_a_run():
    """Find a single run and return it"""
    data = json.loads(request.data)

    node_dict = node_collection_manager.pick_node(kinds=data["kinds"])

    return make_success_response({"node": node_dict})


@app.route('/plynx/api/v0/update_run', methods=['POST'])
@handle_errors
def update_run():
    """Update an entry in /runs collections"""
    data = json.loads(request.data)

    node = Node.from_dict(data['node'])
    app.logger.info(f"updating run {node._id} with node_running_status {node.node_running_status}")     # pylint: disable=no-member

    node.save(collection=Collections.RUNS)
    return make_success_response()


@app.route('/plynx/api/v0/get_run_cancelations', methods=['POST'])
def get_run_cancelations():
    """Ask the server if there is a cancelation"""
    data = json.loads(request.data)
    run_ids = data["run_ids"]

    run_cancellations = list(run_cancellation_manager.get_run_cancellations())
    run_cancellation_ids = set(map(lambda rc: rc.run_id, run_cancellations)) & set(run_ids)

    return make_success_response({"run_ids_to_cancel": list(run_cancellation_ids)})
