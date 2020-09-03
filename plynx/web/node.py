from __future__ import absolute_import
import json
from flask import request, g
from plynx.db.node import Node
from plynx.db.group import Group
import plynx.db.node_collection_manager
import plynx.db.run_cancellation_manager
import plynx.base.hub
import plynx.utils.plugin_manager
from plynx.web.common import app, requires_auth, make_success_response, make_fail_response, make_permission_denied, handle_errors
from plynx.utils.common import to_object_id
from plynx.constants import NodeStatus, NodePostAction, NodePostStatus, Collections, NodeClonePolicy, NodeVirtualCollection, IAMPolicies

PAGINATION_QUERY_KEYS = {'per_page', 'offset', 'status', 'hub', 'node_kinds', 'search', 'user_id'}

node_collection_managers = {
    collection: plynx.db.node_collection_manager.NodeCollectionManager(collection=collection)
    for collection in [Collections.TEMPLATES, Collections.RUNS, Collections.GROUPS]
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
def post_search_nodes(collection):
    query = json.loads(request.data)
    app.logger.debug(request.data)

    query['user_id'] = to_object_id(g.user._id)

    virtual_collection = query.pop('virtual_collection', None)

    if len(query.keys() - PAGINATION_QUERY_KEYS):
        return make_fail_response('Unknown keys: `{}`'.format(query.keys() - PAGINATION_QUERY_KEYS)), 400

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
def get_nodes(collection, node_link=None):
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
        node = executor_manager.kind_to_executor_class[kind].get_default_node(
            is_workflow=kind in workflow_manager.kind_to_workflow_dict
        )
        if isinstance(node, tuple):
            data = node[0].to_dict()
            tour_steps = node[1]
        else:
            data = node.to_dict()
            tour_steps = []
        data['kind'] = kind
        return make_success_response({
            'node': data,
            'tour_steps': tour_steps,
            'plugins_dict': PLUGINS_DICT,
            })
    elif node_link in workflow_manager.kind_to_workflow_dict and collection == Collections.GROUPS:
        # TODO move group to a separate class
        group_dict = Group().to_dict()
        group_dict['kind'] = node_link
        return make_success_response({
            'group': group_dict,
            'plugins_dict': PLUGINS_DICT,
            })
    else:
        # when node_link is an id of the object
        try:
            node_id = to_object_id(node_link)
        except Exception:
            return make_fail_response('Invalid ID'), 404
        if collection == Collections.GROUPS:
            # TODO move group to a separate class
            group = node_collection_managers[collection].get_db_object(node_id, user_id)
            if group:
                return make_success_response({
                    'group': group,
                    'plugins_dict': PLUGINS_DICT,
                    })
            else:
                make_fail_response('Group `{}` was not found'.format(node_link)), 404
        node = node_collection_managers[collection].get_db_node(node_id, user_id)
        app.logger.debug(node)

        if node:
            is_owner = node['author'] == user_id
            kind = node['kind']
            if kind in workflow_manager.kind_to_workflow_dict and not can_view_workflows:
                return make_permission_denied()
            if kind in operation_manager.kind_to_operation_dict and not can_view_operations:
                return make_permission_denied()
            if kind in workflow_manager.kind_to_workflow_dict and not can_view_others_workflows and not is_owner:
                return make_permission_denied()
            if kind in operation_manager.kind_to_operation_dict and not can_view_others_operations and not is_owner:
                return make_permission_denied()
            return make_success_response({
                'node': node,
                'plugins_dict': PLUGINS_DICT,
                })
        else:
            return make_fail_response('Node `{}` was not found'.format(node_link)), 404


@app.route('/plynx/api/v0/<collection>', methods=['POST'])
@handle_errors
@requires_auth
def post_node(collection):
    app.logger.debug(request.data)

    data = json.loads(request.data)

    node = Node.from_dict(data['node'])
    node.starred = False
    action = data['action']
    db_node = node_collection_managers[collection].get_db_node(node._id, g.user._id)

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

    if action == NodePostAction.SAVE:
        if (is_workflow and not can_create_workflows) or (not is_workflow and not can_create_operations):
            return make_permission_denied('You do not have permission to save this object')

        if node.node_status != NodeStatus.CREATED:
            return make_fail_response('Cannot save node with status `{}`'.format(node.node_status))

        if is_author or is_admin or (is_workflow and can_modify_others_workflows):
            node.save(force=True)
        else:
            return make_permission_denied('Only the owners or users with CAN_MODIFY_OTHERS_WORKFLOWS role can save it')

    elif action == NodePostAction.APPROVE:
        if is_workflow:
            return make_fail_response('Invalid action for a workflow'), 400
        if node.node_status != NodeStatus.CREATED:
            return make_fail_response('Node status `{}` expected. Found `{}`'.format(NodeStatus.CREATED, node.node_status))
        validation_error = executor_manager.kind_to_executor_class[node.kind](node).validate()
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
            return make_fail_response('Node status `{}` expected. Found `{}`'.format(NodeStatus.CREATED, node.node_status))
        validation_error = executor_manager.kind_to_executor_class[node.kind](node).validate()
        if validation_error:
            return make_success_response({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })

        node = node.clone(NodeClonePolicy.NODE_TO_RUN)
        node.author = g.user._id
        if is_admin or can_run_workflows:
            node.save(collection=Collections.RUNS)
        else:
            return make_permission_denied('You do not have CAN_RUN_WORKFLOWS role')

        return make_success_response({
                'status': NodePostStatus.SUCCESS,
                'message': 'Run(_id=`{}`) successfully created'.format(str(node._id)),
                'run_id': str(node._id),
                'url': '/{}/{}'.format(Collections.RUNS, node._id),
            })

    elif action == NodePostAction.CLONE:
        if (is_workflow and not can_create_workflows) or (not is_workflow and not can_create_operations):
            return make_permission_denied('You do not have the role to create an object')
        node_clone_policy = None
        if collection == Collections.TEMPLATES:
            node_clone_policy = NodeClonePolicy.NODE_TO_NODE
        elif collection == Collections.RUNS:
            node_clone_policy = NodeClonePolicy.RUN_TO_NODE

        node = node.clone(node_clone_policy)
        node.save(collection=Collections.TEMPLATES)

        return make_success_response({
                'message': 'Node(_id=`{}`) successfully created'.format(str(node._id)),
                'node_id': str(node._id),
                'url': '/{}/{}'.format(Collections.TEMPLATES, node._id),
            })

    elif action == NodePostAction.VALIDATE:
        validation_error = executor_manager.kind_to_executor_class[node.kind](node).validate()

        if validation_error:
            return make_success_response({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })
    elif action == NodePostAction.DEPRECATE:
        if node.node_status == NodeStatus.CREATED:
            return make_fail_response('Node status `{}` not expected.'.format(node.node_status))

        node.node_status = NodeStatus.DEPRECATED

        if is_author or is_admin:
            node.save(force=True)
        else:
            return make_permission_denied('You are not an author to deprecate it')

    elif action == NodePostAction.MANDATORY_DEPRECATE:
        if node.node_status == NodeStatus.CREATED:
            return make_fail_response('Node status `{}` not expected.'.format(node.node_status))

        node.node_status = NodeStatus.MANDATORY_DEPRECATED

        if is_author or is_admin:
            node.save(force=True)
        else:
            return make_permission_denied('You are not an author to deprecate it')

    elif action == NodePostAction.PREVIEW_CMD:

        return make_success_response({
                'message': 'Successfully created preview',
                'preview_text': executor_manager.kind_to_executor_class[node.kind](node).run(preview=True)
            })

    elif action == NodePostAction.REARRANGE_NODES:
        node.arrange_auto_layout()
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
        return make_fail_response('Unknown action `{}`'.format(action))

    return make_success_response({
            'message': 'Node(_id=`{}`) successfully updated'.format(str(node._id))
        })


@app.route('/plynx/api/v0/groups', methods=['POST'])
@handle_errors
@requires_auth
def post_group():
    app.logger.debug(request.data)

    data = json.loads(request.data)

    group = Group.from_dict(data['group'])
    group.author = g.user._id
    db_group = node_collection_managers[Collections.GROUPS].get_db_object(group._id, g.user._id)
    action = data['action']
    if db_group and db_group['_readonly']:
        return make_fail_response('Permission denied'), 403

    if action == NodePostAction.SAVE:
        group.save(force=True)

    return make_success_response({
            'message': 'Group(_id=`{}`) successfully updated'.format(str(group._id))
        })
