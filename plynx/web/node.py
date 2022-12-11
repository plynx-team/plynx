"""All of the endpoints related to the Nodes or simial DB structures"""
from __future__ import absolute_import

import json
from typing import Optional, Set

import bson.objectid
from flask import g, request

import plynx.base.hub
import plynx.db.node_collection_manager
import plynx.db.run_cancellation_manager
import plynx.utils.plugin_manager
from plynx.constants import Collections, IAMPolicies, NodeClonePolicy, NodePostAction, NodePostStatus, NodeRunningStatus, NodeStatus, NodeVirtualCollection
from plynx.db.node import Node
from plynx.utils import node_utils
from plynx.utils.common import ObjectId, to_object_id
from plynx.utils.thumbnails import apply_thumbnails
from plynx.web.common import app, handle_errors, logger, make_fail_response, make_permission_denied, make_success_response, requires_auth

PAGINATION_QUERY_KEYS = {'per_page', 'offset', 'status', 'hub', 'node_kinds', 'search', 'user_id'}

node_collection_managers = {
    collection: plynx.db.node_collection_manager.NodeCollectionManager(collection=collection)
    for collection in [Collections.TEMPLATES, Collections.RUNS]
}
run_cancellation_manager = plynx.db.run_cancellation_manager.RunCancellationManager()


operation_manager = plynx.utils.plugin_manager.get_operation_manager()
hub_manager = plynx.utils.plugin_manager.get_hub_manager()
workflow_manager = plynx.utils.plugin_manager.get_workflow_manager()
executor_manager = plynx.utils.plugin_manager.get_executor_manager()

PLUGINS_DICT = plynx.utils.plugin_manager.get_plugins_dict()


@app.route('/plynx/api/v0/search_<collection>', methods=['POST'])
@handle_errors
@requires_auth
def post_search_nodes(collection: str):
    """Create a search request in templates or runs"""
    query = json.loads(request.data)
    logger.debug(request.data)

    query['user_id'] = to_object_id(g.user._id)

    virtual_collection = query.pop('virtual_collection', None)

    if len(query.keys() - PAGINATION_QUERY_KEYS):
        return make_fail_response(f"Unknown keys: `{query.keys() - PAGINATION_QUERY_KEYS}`"), 400

    if collection == 'in_hubs':
        hub = query.pop('hub')
        res = hub_manager.kind_to_hub_class[hub].search(plynx.base.hub.Query(**query))
    else:
        if virtual_collection == NodeVirtualCollection.OPERATIONS:
            query['node_kinds'] = list(operation_manager.kind_to_operation_dict.keys())
        elif virtual_collection == NodeVirtualCollection.WORKFLOWS:
            query['node_kinds'] = list(workflow_manager.kind_to_workflow_dict.keys())
        res = node_collection_managers[collection].get_db_objects(**query)

    return make_success_response({
        'items': res['list'],
        'total_count': res['metadata'][0]['total'] if res['metadata'] else 0,
        'plugins_dict': PLUGINS_DICT,
    })


@app.route('/plynx/api/v0/<collection>/<node_link>', methods=['GET'])
@handle_errors
@requires_auth
def get_nodes(collection: str, node_link: Optional[str] = None):
    """Get the Node based on its ID or kind"""
    # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches
    user_id = to_object_id(g.user._id)

    can_view_others_operations = g.user.check_role(IAMPolicies.CAN_VIEW_OTHERS_OPERATIONS)
    can_view_others_workflows = g.user.check_role(IAMPolicies.CAN_VIEW_OTHERS_WORKFLOWS)
    can_view_operations = g.user.check_role(IAMPolicies.CAN_VIEW_OPERATIONS)
    can_view_workflows = g.user.check_role(IAMPolicies.CAN_VIEW_WORKFLOWS)
    can_create_operations = g.user.check_role(IAMPolicies.CAN_CREATE_OPERATIONS)
    can_create_workflows = g.user.check_role(IAMPolicies.CAN_CREATE_WORKFLOWS)

    if node_link in executor_manager.kind_to_executor_class and collection == Collections.TEMPLATES:
        # if node_link is a base node
        # i.e. /templates/basic-bash
        kind = node_link
        if kind in workflow_manager.kind_to_workflow_dict and (not can_view_workflows or not can_create_workflows):
            return make_permission_denied()
        if kind in operation_manager.kind_to_operation_dict and (not can_view_operations or not can_create_operations):
            return make_permission_denied()
        node: Node = executor_manager.kind_to_executor_class[kind].get_default_node(
            is_workflow=kind in workflow_manager.kind_to_workflow_dict
        )
        if isinstance(node, tuple):
            data = node[0].to_dict()
            tour_steps = node[1]
        else:
            data = node.to_dict()
            tour_steps = []

        node.author = user_id
        node.save()
        data['kind'] = kind
        return make_success_response({
            'node': data,
            'tour_steps': tour_steps,
            'plugins_dict': PLUGINS_DICT,
            })
    else:
        # when node_link is an id of the object
        try:
            node_id = to_object_id(node_link)
        except bson.objectid.InvalidId:     # type: ignore
            return make_fail_response('Invalid ID'), 404
        node_dict = node_collection_managers[collection].get_db_node(node_id, user_id)
        if not node_dict:
            return make_fail_response(f"Node `{node_link}` was not found"), 404
        node = Node.from_dict(node_dict)

        is_owner = node.author == user_id
        if node.kind in workflow_manager.kind_to_workflow_dict and not can_view_workflows:
            return make_permission_denied()
        if node.kind in operation_manager.kind_to_operation_dict and not can_view_operations:
            return make_permission_denied()
        if node.kind in workflow_manager.kind_to_workflow_dict and not can_view_others_workflows and not is_owner:
            return make_permission_denied()
        if node.kind in operation_manager.kind_to_operation_dict and not can_view_others_operations and not is_owner:
            return make_permission_denied()

        latest_run_id = node.latest_run_id
        last_run_is_in_finished_status = None
        if collection == Collections.TEMPLATES and latest_run_id:
            node_in_run_dict = node_collection_managers[Collections.RUNS].get_db_node(latest_run_id, user_id)

            if node_in_run_dict:
                node_in_run = Node.from_dict(node_in_run_dict)
                node_utils.augment_node_with_cache(node, node_in_run)
                last_run_is_in_finished_status = NodeRunningStatus.is_finished(node_in_run.node_running_status)
            else:
                logger.warning(f"Failed to load a run with id `{latest_run_id}`")

        apply_thumbnails(node)

        return make_success_response({
            "node": node.to_dict(),
            "plugins_dict": PLUGINS_DICT,
            "last_run_is_in_finished_status": last_run_is_in_finished_status,
            })


@app.route('/plynx/api/v0/<collection>', methods=['POST'])
@handle_errors
@requires_auth
def post_node(collection: str):
    """Post a Node with an action"""
    # TODO: fix disables
    # pylint: disable=too-many-return-statements,too-many-branches,too-many-statements,too-many-locals
    logger.debug(request.data)

    data = json.loads(request.data)

    node: Node = Node.from_dict(data['node'])
    node.starred = False
    action = data['action']
    user_id = g.user._id
    db_node = node_collection_managers[collection].get_db_node(node._id, user_id)

    if db_node:
        if not node.author:
            node.author = db_node['author']
        if node.author != db_node['author']:
            raise Exception("Author of the node does not match the one in the database")
        is_author = db_node['author'] == g.user._id
    else:
        # assign the author
        node.author = g.user._id
        is_author = True

    is_admin = g.user.check_role(IAMPolicies.IS_ADMIN)
    is_workflow = node.kind in workflow_manager.kind_to_workflow_dict

    can_create_operations = g.user.check_role(IAMPolicies.CAN_CREATE_OPERATIONS)
    can_create_workflows = g.user.check_role(IAMPolicies.CAN_CREATE_WORKFLOWS)
    can_modify_others_workflows = g.user.check_role(IAMPolicies.CAN_MODIFY_OTHERS_WORKFLOWS)
    can_run_workflows = g.user.check_role(IAMPolicies.CAN_RUN_WORKFLOWS)

    executor = executor_manager.kind_to_executor_class[node.kind](node)

    if action == NodePostAction.SAVE:
        if (is_workflow and not can_create_workflows) or (not is_workflow and not can_create_operations):
            return make_permission_denied('You do not have permission to save this object')

        if node.node_status != NodeStatus.CREATED:
            return make_fail_response(f"Cannot save node with status `{node.node_status}`")

        if not (is_author or is_admin or (is_workflow and can_modify_others_workflows)):
            return make_permission_denied('Only the owners or users with CAN_MODIFY_OTHERS_WORKFLOWS role can save it')

        if node.auto_run:
            node_in_run, new_node_in_run = node_utils.construct_new_run(node, user_id)
            node_utils.remove_auto_run_disabled(new_node_in_run)

            old_run_stats = node_utils.calc_status_to_node_ids(node_in_run)
            new_run_stats = node_utils.calc_status_to_node_ids(new_node_in_run)

            awaiting_nodes: Set[ObjectId] = set()
            for status in NodeRunningStatus._AWAITING_STATUSES | NodeRunningStatus._FINISHED_STATUSES:
                awaiting_nodes = awaiting_nodes | old_run_stats[status]
            no_need_to_run = node_in_run and \
                len(new_run_stats[NodeRunningStatus.READY] - awaiting_nodes) == 0

            if not no_need_to_run:
                # TODO check permissions
                executor._update_node(new_node_in_run)
                validation_error = executor.validate()

                if validation_error:
                    logger.info("Validation failed. Won't start the run")
                else:
                    executor.launch()

                    if node.latest_run_id:
                        run_cancellation_manager.cancel_run(node.latest_run_id)
                    node.latest_run_id = new_node_in_run._id

        node.save(force=True)

    elif action == NodePostAction.APPROVE:
        if is_workflow:
            return make_fail_response('Invalid action for a workflow'), 400
        if node.node_status != NodeStatus.CREATED:
            return make_fail_response(f"Node status `{NodeStatus.CREATED}` expected. Found `{node.node_status}`")
        validation_error = executor.validate()
        if validation_error:
            return make_success_response({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })

        node.node_status = NodeStatus.READY

        if is_author or is_admin:
            node.save(force=True)
        else:
            return make_permission_denied()

    elif action == NodePostAction.CREATE_RUN:
        if not is_workflow:
            return make_fail_response('Invalid action for an operation'), 400
        if node.node_status != NodeStatus.CREATED:
            return make_fail_response(f"Node status `{NodeStatus.CREATED}` expected. Found `{node.node_status}`")
        validation_error = executor.validate()
        if validation_error:
            return make_success_response({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })

        _, new_node_in_run = node_utils.construct_new_run(node, user_id)
        new_node_in_run.author = g.user._id

        if is_admin or can_run_workflows:
            executor._update_node(new_node_in_run)
            executor.launch()
        else:
            return make_permission_denied('You do not have CAN_RUN_WORKFLOWS role')

        node.latest_run_id = new_node_in_run._id
        node.save(force=True)

        return make_success_response({
                'status': NodePostStatus.SUCCESS,
                'message': f"Run(_id=`{new_node_in_run._id}`) successfully created",
                'run_id': str(new_node_in_run._id),
                'url': f"/{Collections.RUNS}/{new_node_in_run._id}",
            })

    elif action == NodePostAction.CREATE_RUN_FROM_SCRATCH:
        if not is_workflow:
            return make_fail_response('Invalid action for an operation'), 400
        if node.node_status != NodeStatus.CREATED:
            return make_fail_response(f"Node status `{NodeStatus.CREATED}` expected. Found `{node.node_status}`")
        validation_error = executor.validate()
        if validation_error:
            return make_success_response({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })

        node_in_run = node.clone(NodeClonePolicy.NODE_TO_RUN)
        node_in_run.author = g.user._id

        db_node_obj = Node.from_dict(db_node)
        db_node_obj.latest_run_id = node_in_run._id
        db_node_obj.save(force=True)

        if is_admin or can_run_workflows:
            executor._update_node(node_in_run)
            executor.launch()
        else:
            return make_permission_denied('You do not have CAN_RUN_WORKFLOWS role')

        return make_success_response({
                'status': NodePostStatus.SUCCESS,
                'message': f"Run(_id=`{node_in_run._id}`) successfully created",
                'run_id': str(node_in_run._id),
                'url': f"/{Collections.RUNS}/{node_in_run._id}",
            })

    elif action == NodePostAction.CLONE:
        if (is_workflow and not can_create_workflows) or (not is_workflow and not can_create_operations):
            return make_permission_denied('You do not have the role to create an object')
        node_clone_policy: int
        if collection == Collections.TEMPLATES:
            node_clone_policy = NodeClonePolicy.NODE_TO_NODE
        elif collection == Collections.RUNS:
            node_clone_policy = NodeClonePolicy.RUN_TO_NODE
        else:
            raise ValueError(f"Unknown or unexpeted collection `{collection}`")

        node = node.clone(node_clone_policy)
        node.save(collection=Collections.TEMPLATES)

        return make_success_response({
                'message': f"Node(_id=`{node._id}`) successfully created",
                'node_id': str(node._id),
                'url': f"/{Collections.TEMPLATES}/{node._id}",
            })

    elif action == NodePostAction.VALIDATE:
        validation_error = executor.validate()

        if validation_error:
            return make_success_response({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })
    elif action == NodePostAction.DEPRECATE:
        if node.node_status == NodeStatus.CREATED:
            return make_fail_response(f"Node status `{node.node_status}` not expected.")

        node.node_status = NodeStatus.DEPRECATED

        if is_author or is_admin:
            node.save(force=True)
        else:
            return make_permission_denied('You are not an author to deprecate it')

    elif action == NodePostAction.MANDATORY_DEPRECATE:
        if node.node_status == NodeStatus.CREATED:
            return make_fail_response(f"Node status `{node.node_status}` not expected.")

        node.node_status = NodeStatus.MANDATORY_DEPRECATED

        if is_author or is_admin:
            node.save(force=True)
        else:
            return make_permission_denied('You are not an author to deprecate it')

    elif action == NodePostAction.PREVIEW_CMD:

        return make_success_response({
                'message': 'Successfully created preview',
                'preview_text': executor.run(preview=True)
            })

    elif action == NodePostAction.REARRANGE_NODES:
        node_utils.arrange_auto_layout(node)
        return make_success_response({
                'message': 'Successfully created preview',
                'node': node.to_dict(),
            })
    elif action == NodePostAction.UPGRADE_NODES:
        upd = node_collection_managers[collection].upgrade_sub_nodes(node)
        return make_success_response({
                'message': 'Successfully updated nodes',
                'node': node.to_dict(),
                'upgraded_nodes_count': upd,
            })
    elif action == NodePostAction.CANCEL:

        if is_author or is_admin:
            run_cancellation_manager.cancel_run(node._id)
        else:
            return make_permission_denied('You are not an author to cancel the run')

    elif action == NodePostAction.GENERATE_CODE:
        raise NotImplementedError()
    else:
        return make_fail_response(f"Unknown action `{action}`")

    return make_success_response({
            'message': f"Node(_id=`{node._id}`) successfully updated"
        })
