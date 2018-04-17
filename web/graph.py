#!/usr/bin/env python
import json
from db import GraphCollectionManager
from db import Graph
from web.common import app, request, auth, g
from utils.common import to_object_id, JSONEncoder
from collections import defaultdict, OrderedDict
from constants import GraphRunningStatus, GraphPostAction, GraphPostStatus


graph_collection_manager = GraphCollectionManager()


def _make_fail_response(message):
    return JSONEncoder().encode({
        'status': GraphPostStatus.FAILED,
        'message': message
        })


@app.route('/plynx/api/v0/graphs', methods=['GET'])
@app.route('/plynx/api/v0/graphs/<graph_id>', methods=['GET'])
@auth.login_required
def get_graph(graph_id=None):
    if graph_id == 'new':
        return JSONEncoder().encode({
            'data': Graph().to_dict(),
            'status':'success'})
    elif graph_id:
        graph = graph_collection_manager.get_db_graph(graph_id)
        if graph:
            return JSONEncoder().encode({
                'data': graph,
                'status':'success'})
        else:
            return 'Graph was not found', 404
    else:
        query = json.loads(request.args.get('query', "{}"))
        query["author"] = to_object_id(g.user._id)
        graphs_query = {k: v for k, v in query.iteritems() if k in {'per_page', 'offset', 'author'}}
        count_query = {k: v for k, v in query.iteritems() if k in {'author'}}
        return JSONEncoder().encode({
            'graphs': [graph for graph in graph_collection_manager.get_db_graphs(**graphs_query)],
            'total_count': graph_collection_manager.get_db_graphs_count(**count_query),
            'status':'success'})


@app.route('/plynx/api/v0/graphs', methods=['POST'])
@auth.login_required
def post_graph():
    app.logger.debug(request.data)
    try:
        body = json.loads(request.data)['body']

        graph = Graph()
        graph.load_from_dict(body['graph'])
        graph.author = g.user._id
        actions = body['actions']

        for action in actions:
            if action == GraphPostAction.SAVE:
                if graph.graph_running_status != GraphRunningStatus.CREATED:
                    return _make_fail_response('Cannot save graph with status `{}`'.format(graph.graph_running_status))
                graph.save(force=True)

            elif action == GraphPostAction.AUTO_LAYOUT:
                graph.arrange_auto_layout()

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
            else:
                return _make_fail_response('Unknown action `{}`'.format(action))

        return JSONEncoder().encode(
            {
                'status': GraphPostStatus.SUCCESS,
                'message': 'Graph(_id=`{}`) successfully updated'.format(str(graph._id)),
                'graph': graph.to_dict()
            })
    except Exception as e:
        app.logger.error(e)
        return _make_fail_response('Internal error: "{}"'.format(repr(e)))
