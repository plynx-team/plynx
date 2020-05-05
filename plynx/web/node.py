from __future__ import absolute_import
import json
from flask import request, g
from plynx.db.node import Node
from plynx.db.group import Group
import plynx.db.node_collection_manager
import plynx.db.run_cancellation_manager
import plynx.base.hub
import plynx.utils.plugin_manager
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors
from plynx.utils.common import to_object_id, JSONEncoder
from plynx.constants import NodeStatus, NodePostAction, NodePostStatus, Collections, NodeClonePolicy, NodeVirtualCollection

PAGINATION_QUERY_KEYS = {'per_page', 'offset', 'status', 'hub', 'node_kinds', 'search', 'user_id'}
PERMITTED_READONLY_POST_ACTIONS = {
    NodePostAction.VALIDATE,
    NodePostAction.PREVIEW_CMD,
    NodePostAction.CLONE,
    NodePostAction.REARRANGE_NODES,
}

node_collection_managers = {
    collection: plynx.db.node_collection_manager.NodeCollectionManager(collection=collection)
    for collection in [Collections.TEMPLATES, Collections.RUNS, Collections.GROUPS]
}
run_cancellation_manager = plynx.db.run_cancellation_manager.RunCancellationManager()

resource_manager = plynx.utils.plugin_manager.get_resource_manager()
operation_manager = plynx.utils.plugin_manager.get_operation_manager()
hub_manager = plynx.utils.plugin_manager.get_hub_manager()
workflow_manager = plynx.utils.plugin_manager.get_workflow_manager()
executor_manager = plynx.utils.plugin_manager.get_executor_manager()

PLUGINS_DICT = {
    'resources_dict': resource_manager.kind_to_resource_dict,
    'operations_dict': operation_manager.kind_to_operation_dict,
    'hubs_dict': hub_manager.kind_to_hub_dict,
    'workflows_dict': workflow_manager.kind_to_workflow_dict,
    'executors_info': executor_manager.kind_info,
}


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

    return JSONEncoder().encode({
        'items': res['list'],
        'total_count': res['metadata'][0]['total'] if res['metadata'] else 0,
        'plugins_dict': PLUGINS_DICT,
        'status': 'success'})


@app.route('/plynx/api/v0/<collection>/<node_link>', methods=['GET'])
@handle_errors
@requires_auth
def get_nodes(collection, node_link=None):
    user_id = to_object_id(g.user._id)
    # if node_link is a base node
    if node_link in executor_manager.kind_to_executor_class and collection == Collections.TEMPLATES:
        kind = node_link
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
        return JSONEncoder().encode({
            'node': data,
            'tour_steps': tour_steps,
            'plugins_dict': PLUGINS_DICT,
            'status': 'success'})
    elif node_link in workflow_manager.kind_to_workflow_dict and collection == Collections.GROUPS:
        # TODO move group to a separate class
        group_dict = Group().to_dict()
        group_dict['kind'] = node_link
        return JSONEncoder().encode({
            'group': group_dict,
            'plugins_dict': PLUGINS_DICT,
            'status': 'success'})
    else:
        try:
            node_id = to_object_id(node_link)
        except Exception:
            return make_fail_response('Invalid ID'), 404
        if collection == Collections.GROUPS:
            # TODO move group to a separate class
            group = node_collection_managers[collection].get_db_object(node_id, user_id)
            if group:
                return JSONEncoder().encode({
                    'group': group,
                    'plugins_dict': PLUGINS_DICT,
                    'status': 'success',
                    })
            else:
                make_fail_response('Group `{}` was not found'.format(node_link)), 404
        node = node_collection_managers[collection].get_db_node(node_id, user_id)
        app.logger.debug(node)
        if node:
            return JSONEncoder().encode({
                'node': node,
                'plugins_dict': PLUGINS_DICT,
                'status': 'success'})
        else:
            return make_fail_response('Node `{}` was not found'.format(node_link)), 404


@app.route('/plynx/api/v0/<collection>', methods=['POST'])
@handle_errors
@requires_auth
def post_node(collection):
    app.logger.debug(request.data)

    data = json.loads(request.data)

    node = Node.from_dict(data['node'])
    node.author = g.user._id
    node.starred = False
    db_node = node_collection_managers[collection].get_db_node(node._id, g.user._id)
    action = data['action']
    if db_node and db_node['_readonly'] and action not in PERMITTED_READONLY_POST_ACTIONS:
        return make_fail_response('Permission denied'), 403

    if action == NodePostAction.SAVE:
        if node.node_status != NodeStatus.CREATED and node.base_node_name != 'file':
            return make_fail_response('Cannot save node with status `{}`'.format(node.node_status))

        node.save(force=True)

    elif action == NodePostAction.APPROVE:
        if node.node_status != NodeStatus.CREATED:
            return make_fail_response('Node status `{}` expected. Found `{}`'.format(NodeStatus.CREATED, node.node_status))
        validation_error = executor_manager.kind_to_executor_class[node.kind](node).validate()
        if validation_error:
            return JSONEncoder().encode({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })

        node.node_status = NodeStatus.READY
        node.save(force=True)

    elif action == NodePostAction.CREATE_RUN:
        if node.node_status != NodeStatus.CREATED:
            return make_fail_response('Node status `{}` expected. Found `{}`'.format(NodeStatus.CREATED, node.node_status))
        validation_error = executor_manager.kind_to_executor_class[node.kind](node).validate()
        if validation_error:
            return JSONEncoder().encode({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })

        node = node.clone(NodeClonePolicy.NODE_TO_RUN)
        node.save(collection=Collections.RUNS)
        return JSONEncoder().encode(
            {
                'status': NodePostStatus.SUCCESS,
                'message': 'Run(_id=`{}`) successfully created'.format(str(node._id)),
                'run_id': str(node._id),
                'url': '/{}/{}'.format(Collections.RUNS, node._id),
            })

    elif action == NodePostAction.CLONE:
        node_clone_policy = None
        if collection == Collections.TEMPLATES:
            node_clone_policy = NodeClonePolicy.NODE_TO_NODE
        elif collection == Collections.RUNS:
            node_clone_policy = NodeClonePolicy.RUN_TO_NODE

        node = node.clone(node_clone_policy)
        node.save(collection=Collections.TEMPLATES)

        return JSONEncoder().encode(
            {
                'status': NodePostStatus.SUCCESS,
                'message': 'Node(_id=`{}`) successfully created'.format(str(node._id)),
                'node_id': str(node._id),
                'url': '/{}/{}'.format(Collections.TEMPLATES, node._id),
            })

    elif action == NodePostAction.VALIDATE:
        validation_error = executor_manager.kind_to_executor_class[node.kind](node).validate()

        if validation_error:
            return JSONEncoder().encode({
                'status': NodePostStatus.VALIDATION_FAILED,
                'message': 'Node validation failed',
                'validation_error': validation_error.to_dict()
            })
    elif action == NodePostAction.DEPRECATE:
        if node.node_status == NodeStatus.CREATED:
            return make_fail_response('Node status `{}` not expected.'.format(node.node_status))

        node.node_status = NodeStatus.DEPRECATED
        node.save(force=True)
    elif action == NodePostAction.MANDATORY_DEPRECATE:
        if node.node_status == NodeStatus.CREATED:
            return make_fail_response('Node status `{}` not expected.'.format(node.node_status))

        node.node_status = NodeStatus.MANDATORY_DEPRECATED
        node.save(force=True)
    elif action == NodePostAction.PREVIEW_CMD:

        return JSONEncoder().encode(
            {
                'status': NodePostStatus.SUCCESS,
                'message': 'Successfully created preview',
                'preview_text': executor_manager.kind_to_executor_class[node.kind](node).run(preview=True)
            })

    elif action == NodePostAction.REARRANGE_NODES:
        node.arrange_auto_layout()
        return JSONEncoder().encode(dict(
            {
                'status': NodePostStatus.SUCCESS,
                'message': 'Successfully created preview',
                'node': node.to_dict(),
            }
        ))
    elif action == NodePostAction.UPGRADE_NODES:
        upd = node_collection_managers[collection].upgrade_sub_nodes(node)
        return JSONEncoder().encode(dict(
            {
                'status': NodePostStatus.SUCCESS,
                'message': 'Successfully updated nodes',
                'node': node.to_dict(),
                'upgraded_nodes_count': upd,
            }
        ))
    elif action == NodePostAction.CANCEL:
        run_cancellation_manager.cancel_run(node._id)
    elif action == NodePostAction.GENERATE_CODE:
        raise NotImplementedError()
    else:
        return make_fail_response('Unknown action `{}`'.format(action))

    return JSONEncoder().encode(
        {
            'status': NodePostStatus.SUCCESS,
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
    if db_group and db_group['_readonly'] and action not in PERMITTED_READONLY_POST_ACTIONS:
        return make_fail_response('Permission denied'), 403

    if action == NodePostAction.SAVE:
        group.save(force=True)

    return JSONEncoder().encode(
        {
            'status': NodePostStatus.SUCCESS,
            'message': 'Group(_id=`{}`) successfully updated'.format(str(group._id))
        })
