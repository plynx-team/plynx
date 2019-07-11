import json
import traceback
from plynx.db.graph import Graph
from plynx.db.graph_collection_manager import GraphCollectionManager
from plynx.db.graph_cancellation_manager import GraphCancellationManager
from flask import request, g
from plynx.web.common import app, requires_auth, make_fail_response, handle_errors
from plynx.plugins.managers import resource_manager
from plynx.utils.common import JSONEncoder
from plynx.constants import GraphRunningStatus, GraphPostAction, GraphPostStatus
from plynx.utils.config import get_web_config


graph_collection_manager = GraphCollectionManager()
graph_cancellation_manager = GraphCancellationManager()
WEB_CONFIG = get_web_config()
PAGINATION_QUERY_KEYS = {'per_page', 'offset', 'search', 'status'}
PERMITTED_READONLY_POST_ACTIONS = {
    GraphPostAction.VALIDATE,
    GraphPostAction.AUTO_LAYOUT,
    GraphPostAction.GENERATE_CODE,
    GraphPostAction.UPGRADE_NODES,
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


@app.route('/plynx/api/v0/graphs', methods=['POST'])
@handle_errors
@requires_auth
def post_graph():
    app.logger.debug(request.data)
    body = json.loads(request.data)['body']

    graph = Graph.from_dict(body['graph'])
    graph.author = g.user._id
    actions = body['actions']
    extra_response = {}
    db_graph = graph_collection_manager.get_db_graph(graph._id, g.user._id)
    if db_graph and db_graph['_readonly'] and set(actions) - PERMITTED_READONLY_POST_ACTIONS:
        return make_fail_response('Permission denied'), 403

    for action in actions:
        if action == GraphPostAction.SAVE:
            if graph.graph_running_status != GraphRunningStatus.CREATED:
                return make_fail_response('Cannot save graph with status `{}`'.format(graph.graph_running_status))
            graph.save(force=True)

        elif action == GraphPostAction.AUTO_LAYOUT:
            graph.arrange_auto_layout()

        elif action == GraphPostAction.UPGRADE_NODES:
            upd = graph_collection_manager.upgrade_nodes(graph)
            extra_response['upgraded_nodes_count'] = upd

        elif action == GraphPostAction.APPROVE:
            if graph.graph_running_status != GraphRunningStatus.CREATED:
                return make_fail_response('Graph status `{}` expected. Found `{}`'.format(GraphRunningStatus.CREATED, graph.graph_running_status))

            validation_error = graph.get_validation_error()
            if validation_error:
                return JSONEncoder().encode({
                    'status': GraphPostStatus.VALIDATION_FAILED,
                    'message': 'Graph validation failed',
                    'validation_error': validation_error.to_dict()
                })

            graph.graph_running_status = GraphRunningStatus.READY
            graph.save(force=True)

        elif action == GraphPostAction.VALIDATE:
            validation_error = graph.get_validation_error()

            if validation_error:
                return JSONEncoder().encode({
                    'status': GraphPostStatus.VALIDATION_FAILED,
                    'message': 'Graph validation failed',
                    'validation_error': validation_error.to_dict()
                })
        elif action == GraphPostAction.CANCEL:
            if graph.graph_running_status not in [
                    GraphRunningStatus.RUNNING,
                    GraphRunningStatus.FAILED_WAITING
                    ]:
                return make_fail_response('Graph status `{}` expected. Found `{}`'.format(GraphRunningStatus.RUNNING, graph.graph_running_status))
            graph_cancellation_manager.cancel_graph(graph._id)
        elif action == GraphPostAction.GENERATE_CODE:
            code = graph.generate_code()
            return JSONEncoder().encode({
                'status': GraphPostStatus.SUCCESS,
                'message': 'Graph code generated',
                'code': code,
            })
        else:
            return make_fail_response('Unknown action `{}`'.format(action))

    return JSONEncoder().encode(dict(
        {
            'status': GraphPostStatus.SUCCESS,
            'message': 'Graph(_id=`{}`) successfully updated'.format(str(graph._id)),
            'graph': graph.to_dict(),
            'url': '{}/graphs/{}'.format(WEB_CONFIG.endpoint.rstrip('/'), str(graph._id))
        }, **extra_response))
