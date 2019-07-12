import json
from plynx.db.graph import Graph
from plynx.db.graph_collection_manager import GraphCollectionManager
from plynx.db.graph_cancellation_manager import GraphCancellationManager
from flask import request, g
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors
from plynx.plugins.managers import resource_manager
from plynx.utils.common import JSONEncoder, update_dict_recursively
from plynx.constants import GraphRunningStatus, GraphPostAction, GraphPostStatus
from plynx.utils.config import get_web_config


graph_collection_manager = GraphCollectionManager()
graph_cancellation_manager = GraphCancellationManager()
WEB_CONFIG = get_web_config()
PAGINATION_QUERY_KEYS = {'per_page', 'offset', 'search', 'status'}
PERMITTED_READONLY_POST_ACTIONS = {
    GraphPostAction.VALIDATE,
    GraphPostAction.REARRANGE,
    GraphPostAction.GENERATE_CODE,
    GraphPostAction.UPGRADE_NODES,
    GraphPostAction.CLONE,
}


@app.route('/plynx/api/v0/search_graphs', methods=['POST'])
@handle_errors
@requires_auth
def post_search_graphs():
    app.logger.debug(request.data)
    query = json.loads(request.data)
    if len(query.keys() - PAGINATION_QUERY_KEYS):
        return make_fail_response('Unknown keys: `{}`'.format(query.keys() - PAGINATION_QUERY_KEYS)), 400

    res = graph_collection_manager.get_db_graphs(**query)

    return JSONEncoder().encode({
        'graphs': res['list'],
        'total_count': res['metadata'][0]['total'] if res['metadata'] else 0,
        'status': 'success'})


@app.route('/plynx/api/v0/graphs/<graph_id>', methods=['GET'])
@handle_errors
@requires_auth
def get_graph(graph_id=None):
    if graph_id == 'new':
        return JSONEncoder().encode({
            'data': Graph().to_dict(),
            'status': 'success',
            'resources_dict': resource_manager.resources_dict,
            })
    else:
        graph = graph_collection_manager.get_db_graph(graph_id)
        if graph:
            return JSONEncoder().encode({
                'data': graph,
                'status': 'success',
                'resources_dict': resource_manager.resources_dict,
                })
        else:
            return make_fail_response('Graph was not found'), 404


def _perform_graph_actions(graph, actions):
    graph.author = g.user._id
    db_graph = graph_collection_manager.get_db_graph(graph._id, g.user._id)
    if db_graph and db_graph['_readonly'] and set(actions) - PERMITTED_READONLY_POST_ACTIONS:
        return make_fail_response('Permission denied'), 403
    extra_response = {}

    response_status = GraphPostStatus.SUCCESS
    response_message = 'Actions completed with Graph(_id=`{}`)'.format(str(graph._id))

    for action in actions:
        if action == GraphPostAction.SAVE:
            if graph.graph_running_status != GraphRunningStatus.CREATED:
                return make_fail_response('Cannot save graph with status `{}`'.format(graph.graph_running_status))
            graph.save(force=True)

        elif action == GraphPostAction.REARRANGE:
            graph.arrange_auto_layout()

        elif action == GraphPostAction.UPGRADE_NODES:
            upd = graph_collection_manager.upgrade_nodes(graph)
            extra_response['upgraded_nodes_count'] = upd

        elif action == GraphPostAction.APPROVE:
            if graph.graph_running_status != GraphRunningStatus.CREATED:
                return make_fail_response('Graph status `{}` expected. Found `{}`'.format(GraphRunningStatus.CREATED, graph.graph_running_status))

            validation_error = graph.get_validation_error()
            if validation_error:
                response_status = GraphPostStatus.VALIDATION_FAILED
                response_message = 'Graph validation failed'
                extra_response['validation_error'] = validation_error.to_dict()
            else:
                graph.graph_running_status = GraphRunningStatus.READY
                graph.save(force=True)

        elif action == GraphPostAction.VALIDATE:
            validation_error = graph.get_validation_error()

            if validation_error:
                response_status = GraphPostStatus.VALIDATION_FAILED
                response_message = 'Graph validation failed'
                extra_response['validation_error'] = validation_error.to_dict()
        elif action == GraphPostAction.CANCEL:
            if graph.graph_running_status not in [
                    GraphRunningStatus.RUNNING,
                    GraphRunningStatus.FAILED_WAITING
                    ]:
                return make_fail_response('Graph status `{}` expected. Found `{}`'.format(GraphRunningStatus.RUNNING, graph.graph_running_status))
            graph_cancellation_manager.cancel_graph(graph._id)
        elif action == GraphPostAction.GENERATE_CODE:
            extra_response['code'] = graph.generate_code()
        elif action == GraphPostAction.CLONE:
            graph = graph.clone()
            graph.save()
            extra_response['new_graph_id'] = graph._id
        else:
            return make_fail_response('Unknown action `{}`'.format(action))

    return JSONEncoder().encode(dict(
        {
            'status': response_status,
            'message': response_message,
            'graph': graph.to_dict(),
            'url': '{}/graphs/{}'.format(WEB_CONFIG.endpoint.rstrip('/'), str(graph._id))
        }, **extra_response))


@app.route('/plynx/api/v0/graphs', methods=['POST'])
@handle_errors
@requires_auth
def post_graph():
    app.logger.debug(request.data)
    data = json.loads(request.data)
    graph = Graph.from_dict(data['graph'])
    actions = data['actions']
    return _perform_graph_actions(graph, actions)


@app.route('/plynx/api/v0/graphs/<graph_id>/<action>', methods=['POST'])
@handle_errors
@requires_auth
def post_graph_action(graph_id, action):
    graph_dict = graph_collection_manager.get_db_graph(graph_id)
    if not graph_dict:
        return make_fail_response('Graph was not found'), 404

    return _perform_graph_actions(Graph.from_dict(graph_dict), [action.upper()])


@app.route('/plynx/api/v0/graphs/<graph_id>/update', methods=['PATCH'])
@handle_errors
@requires_auth
def update_graph(graph_id):
    app.logger.debug(request.data)
    data = json.loads(request.data)
    if not data:
        return make_fail_response('Expected json data'), 400

    graph_dict = graph_collection_manager.get_db_graph(graph_id, g.user._id)
    if not graph_dict:
        return make_fail_response('Graph was not found'), 404
    if graph_dict['_readonly']:
        return make_fail_response('Permission denied'), 403

    if graph_dict['graph_running_status'] != GraphRunningStatus.CREATED:
        return make_fail_response('Cannot save graph with status `{}`'.format(graph.graph_running_status))

    update_dict_recursively(graph_dict, data)

    graph = Graph.from_dict(graph_dict)
    graph.save()

    return JSONEncoder().encode({
            'status': 'success',
            'message': 'Successfully updated',
            'graph': graph.to_dict(),
        })
