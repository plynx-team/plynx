import json
from plynx.db.input import InputValue
from plynx.db.parameter import Parameter
from plynx.db.node import Node
from plynx.db.node_collection_manager import NodeCollectionManager
from plynx.db.graph import Graph
from plynx.db.graph_collection_manager import GraphCollectionManager
from plynx.db.graph_cancellation_manager import GraphCancellationManager
from flask import request, g
from plynx.web.common import app, requires_auth, make_fail_response, make_success_response, handle_errors
from plynx.plugins.managers import resource_manager
from plynx.utils.common import JSONEncoder, update_dict_recursively, ObjectId
from plynx.constants import GraphRunningStatus, GraphPostAction, GraphPostStatus, GraphNodePostAction
from plynx.utils.config import get_web_config


node_collection_manager = NodeCollectionManager()
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
        'items': res['list'],
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
        return make_fail_response('Cannot save graph with status `{}`'.format(graph_dict['graph_running_status']))

    update_dict_recursively(graph_dict, data)

    graph = Graph.from_dict(graph_dict)
    graph.save()

    return JSONEncoder().encode({
            'status': 'success',
            'message': 'Successfully updated',
            'graph': graph.to_dict(),
        })


def _find_nodes(graph, *node_ids):
    res = [None] * len(node_ids)
    node_ids_map = {ObjectId(node_id): ii for ii, node_id in enumerate(node_ids)}
    if len(node_ids_map) != len(node_ids):
        raise ValueError("Duplicated node ids found")
    for node in graph.nodes:
        node_id = ObjectId(node._id)
        if node_id in node_ids_map:
            res[node_ids_map[node_id]] = node
    return res


@app.route('/plynx/api/v0/graphs/<graph_id>/nodes/<action>', methods=['GET'])
@handle_errors
@requires_auth
def get_graph_node_action(graph_id, action):
    graph_dict = graph_collection_manager.get_db_graph(graph_id, g.user._id)
    if not graph_dict:
        return make_fail_response('Graph was not found'), 404

    if action == GraphNodePostAction.LIST_NODES:
        return make_success_response(nodes=graph_dict['nodes'])
    else:
        return make_fail_response('Unknown action `{}`. Try POST method.'.format(action)), 400


@app.route('/plynx/api/v0/graphs/<graph_id>/nodes/<action>', methods=['POST'])
@handle_errors
@requires_auth
def post_graph_node_action(graph_id, action):
    graph_dict = graph_collection_manager.get_db_graph(graph_id, g.user._id)
    if not graph_dict:
        return make_fail_response('Graph was not found'), 404

    if graph_dict['_readonly']:
        return make_fail_response('Permission denied'), 403

    if not request.data:
        return make_fail_response('Empty body'), 400

    data = json.loads(request.data)
    graph = Graph.from_dict(graph_dict)

    if action == GraphNodePostAction.INSERT_NODE:
        node_id = data.get('node_id', None)
        x, y = int(data.get('x', 0)), int(data.get('y', 0))

        node_dict = node_collection_manager.get_db_node(node_id)
        if not node_dict:
            return make_fail_response('Node was not found'), 404
        node = Node.from_dict(node_dict)
        node.x, node.y = x, y
        node.parent_node = node._id
        node._id = ObjectId()
        graph.nodes.append(node)
        graph.save()

        return make_success_response(node=node.to_dict())
    elif action == GraphNodePostAction.REMOVE_NODE:
        node_id = ObjectId(data.get('node_id', None))
        node_index = -1
        for index, node in enumerate(graph.nodes):
            for input in node.inputs:
                input.values = [value for value in input.values if ObjectId(value.node_id) != node_id]
            if ObjectId(node._id) == node_id:
                node_index = index
        if node_index < 0:
            return make_fail_response('Node was not found'), 404
        del graph.nodes[node_index]
        graph.save()
        return make_success_response('Node removed')
    elif action == GraphNodePostAction.CHANGE_PARAMETER:
        node_id = data.get('node_id', None)
        parameter_name = data.get('parameter_name', None)
        parameter_value = data.get('parameter_value', None)
        if parameter_name is None:
            return make_fail_response('No parameter name'), 400
        if parameter_value is None:
            return make_fail_response('No parameter value'), 400

        node, = _find_nodes(graph, node_id)
        if not node:
            return make_fail_response('Node was not found'), 404

        for parameter in node.parameters:
            if parameter.name == parameter_name:
                parameter_dict = parameter.to_dict()
                parameter_dict['value'] = parameter_value

                parameter.value = Parameter(obj_dict=parameter_dict).value
        graph.save()
        return make_success_response('Parameter updated')
    elif action in (GraphNodePostAction.CREATE_LINK, GraphNodePostAction.REMOVE_LINK):
        for field in ['from', 'to']:
            for sub_field in ['node_id', 'resource']:
                if field not in data:
                    return make_fail_response('`{}` is missing'.format(field)), 400
                if sub_field not in data[field]:
                    return make_fail_response('`{}.{}` is missing'.format(field, sub_field)), 400
        from_node_id = data['from']['node_id']
        from_resource = data['from']['resource']
        to_node_id = data['to']['node_id']
        to_resource = data['to']['resource']

        from_node, to_node = _find_nodes(graph, from_node_id, to_node_id)
        if not from_node or not to_node:
            return make_fail_response('Node was not found'), 404

        from_output = None
        to_input = None
        for output in from_node.outputs:
            if output.name == from_resource:
                from_output = output
                break
        for input in to_node.inputs:
            if input.name == to_resource:
                to_input = input
                break
        if not from_output or not to_input:
            return make_fail_response('Input or output not found'), 404

        if action == GraphNodePostAction.CREATE_LINK:
            # TODO graph.validate() it
            if from_output.file_type not in to_input.file_types and 'file' not in to_input.file_types:
                return make_fail_response('Incompatible types'), 400
            # TODO graph.validate() it
            if to_input.max_count > 0 and len(to_input.values) >= to_input.max_count:
                return make_fail_response('Number of inputs reached the limit'), 400

            new_input_value = InputValue()
            new_input_value.node_id = from_node_id
            new_input_value.output_id = from_resource
            # TODO graph.validate() it
            for value in to_input.values:
                if value.node_id == from_node_id and value.output_id == from_resource:
                    return make_fail_response('Link already exists'), 400
            to_input.values.append(new_input_value)
        elif action == GraphNodePostAction.REMOVE_LINK:
            rm_index = -1
            # TODO graph.validate() it
            for index, value in enumerate(to_input.values):
                if value.node_id == from_node_id and value.output_id == from_resource:
                    rm_index = index
                    break
            if rm_index < 0:
                return make_fail_response('Link not found'), 404
            del to_input.values[rm_index]

        graph.save()
        return make_success_response('Completed')
    else:
        return make_fail_response('Unknown action `{}`'.format(action)), 400

    return 'ok'
