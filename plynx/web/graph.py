#!/usr/bin/env python
import json
import traceback
from plynx.db import GraphCollectionManager, Graph
from plynx.db import GraphCancellationManager
from flask import request, g
from plynx.web import app, requires_auth
from plynx.utils.common import to_object_id, JSONEncoder
from plynx.constants import GraphRunningStatus, GraphPostAction, GraphPostStatus
from plynx.utils.config import get_web_config


graph_collection_manager = GraphCollectionManager()
graph_cancellation_manager = GraphCancellationManager()
WEB_CONFIG = get_web_config()
COUNT_QUERY_KEYS = {'author', 'search', 'status'}
PAGINATION_QUERY_KEYS = COUNT_QUERY_KEYS.union({'per_page', 'offset', 'recent'})


def _make_fail_response(message):
    return JSONEncoder().encode({
        'status': GraphPostStatus.FAILED,
        'message': message
    })


@app.route('/plynx/api/v0/graphs', methods=['GET'])
@app.route('/plynx/api/v0/graphs/<graph_id>', methods=['GET'])
@requires_auth
def get_graph(graph_id=None):
    if graph_id == 'new':
        return JSONEncoder().encode({
            'data': Graph().to_dict(),
            'status': 'success'})
    elif graph_id:
        graph = graph_collection_manager.get_db_graph(graph_id)
        if graph:
            return JSONEncoder().encode({
                'data': graph,
                'status': 'success'})
        else:
            return 'Graph was not found', 404
    else:
        query = json.loads(request.args.get('query', "{}"))
        query["author"] = to_object_id(g.user._id)
        count_query = {k: v for k, v in query.items() if k in COUNT_QUERY_KEYS}
        graphs_query = {k: v for k, v in query.items() if k in PAGINATION_QUERY_KEYS}
        return JSONEncoder().encode({
            'graphs': [graph for graph in graph_collection_manager.get_db_graphs(**graphs_query)],
            'total_count': graph_collection_manager.get_db_graphs_count(**count_query),
            'status': 'success'})


@app.route('/plynx/api/v0/graphs', methods=['POST'])
@requires_auth
def post_graph():
    app.logger.debug(request.data)
    try:
        body = json.loads(request.data)['body']

        graph = Graph.from_dict(body['graph'])
        graph.author = g.user._id
        actions = body['actions']
        extra_response = {}

        for action in actions:
            if action == GraphPostAction.SAVE:
                if graph.graph_running_status != GraphRunningStatus.CREATED:
                    return _make_fail_response('Cannot save graph with status `{}`'.format(graph.graph_running_status))
                graph.save(force=True)

            elif action == GraphPostAction.AUTO_LAYOUT:
                graph.arrange_auto_layout()

            elif action == GraphPostAction.UPGRADE_NODES:
                upd = graph_collection_manager.upgrade_nodes(graph)
                extra_response['upgraded_nodes_count'] = upd

            elif action == GraphPostAction.APPROVE:
                if graph.graph_running_status != GraphRunningStatus.CREATED:
                    return _make_fail_response('Graph status `{}` expected. Found `{}`'.format(GraphRunningStatus.CREATED, graph.graph_running_status))

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
                    return _make_fail_response('Graph status `{}` expected. Found `{}`'.format(GraphRunningStatus.RUNNING, graph.graph_running_status))
                graph_cancellation_manager.cancel_graph(graph._id)
            else:
                return _make_fail_response('Unknown action `{}`'.format(action))

        return JSONEncoder().encode(dict(
            {
                'status': GraphPostStatus.SUCCESS,
                'message': 'Graph(_id=`{}`) successfully updated'.format(str(graph._id)),
                'graph': graph.to_dict(),
                'url': '{}/graphs/{}'.format(WEB_CONFIG.endpoint.rstrip('/'), str(graph._id))
            }, **extra_response))
    except Exception as e:
        app.logger.error(traceback.format_exc())
        return _make_fail_response('Internal error: "{}"'.format(repr(e)))
